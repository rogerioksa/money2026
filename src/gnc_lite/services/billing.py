"""Servico de titulos: contas a receber e contas a pagar."""

from __future__ import annotations

from datetime import date

from gnc_lite.domain.account import Account
from gnc_lite.domain.invoice import Invoice, InvoiceError, InvoiceKind, InvoiceStatus, Settlement
from gnc_lite.domain.money import Money
from gnc_lite.domain.party import Party, PartyType
from gnc_lite.domain.transaction import Split, Transaction
from gnc_lite.services.ledger import Ledger

DEFAULT_RECEIVABLE_CODE = "1.3"
DEFAULT_PAYABLE_CODE = "2.1"
DEFAULT_INCOME_CODE = "4.1"
DEFAULT_EXPENSE_CODE = "5.1"
DEFAULT_CASH_CODE = "1.1"


class BillingService:
    """Emite titulos, registra baixas e lista o que esta em aberto."""

    def __init__(self, ledger: Ledger) -> None:
        self.ledger = ledger
        self.repo = ledger.repo

    # ------------------------------------------------------------------ partes
    def create_party(
        self,
        name: str,
        party_type: PartyType,
        *,
        document: str = "",
        email: str = "",
        phone: str = "",
        notes: str = "",
    ) -> Party:
        party = Party(
            name=name,
            type=party_type,
            document=document,
            email=email,
            phone=phone,
            notes=notes,
        )
        return self.repo.add_party(party)

    def parties(self, party_type: PartyType | None = None) -> list[Party]:
        return self.repo.list_parties(party_type)

    # ----------------------------------------------------------------- titulos
    def issue_receivable(
        self,
        party: Party,
        amount: Money,
        issue_date: date,
        due_date: date,
        *,
        income_account: Account | None = None,
        receivable_account: Account | None = None,
        description: str = "",
    ) -> Invoice:
        income = income_account or self._account(DEFAULT_INCOME_CODE)
        control = receivable_account or self._account(DEFAULT_RECEIVABLE_CODE)
        return self._issue(
            InvoiceKind.RECEIVABLE,
            party,
            amount,
            issue_date,
            due_date,
            income,
            control,
            description,
        )

    def issue_payable(
        self,
        party: Party,
        amount: Money,
        issue_date: date,
        due_date: date,
        *,
        expense_account: Account | None = None,
        payable_account: Account | None = None,
        description: str = "",
    ) -> Invoice:
        expense = expense_account or self._account(DEFAULT_EXPENSE_CODE)
        control = payable_account or self._account(DEFAULT_PAYABLE_CODE)
        return self._issue(
            InvoiceKind.PAYABLE,
            party,
            amount,
            issue_date,
            due_date,
            expense,
            control,
            description,
        )

    def _issue(
        self,
        kind: InvoiceKind,
        party: Party,
        amount: Money,
        issue_date: date,
        due_date: date,
        account: Account,
        control_account: Account,
        description: str,
    ) -> Invoice:
        text = description or f"{kind.label} - {party.name}"
        if kind is InvoiceKind.RECEIVABLE:
            splits = [Split(control_account, amount), Split(account, -amount)]
        else:
            splits = [Split(account, amount), Split(control_account, -amount)]

        transaction = Transaction(
            date=issue_date,
            description=text,
            payee=party.name,
            splits=splits,
        )
        self.ledger.post(transaction)

        invoice = Invoice(
            kind=kind,
            amount=amount,
            issue_date=issue_date,
            due_date=due_date,
            party=party,
            account=account,
            description=text,
            transaction_id=transaction.id,
        )
        return self.repo.add_invoice(invoice)

    def settle(
        self,
        invoice: Invoice,
        settlement_date: date,
        cash_account: Account,
        amount: Money | None = None,
    ) -> Invoice:
        """Registra o recebimento/pagamento (total ou parcial) de um titulo."""
        value = amount if amount is not None else invoice.open_amount
        if value.minor_units <= 0:
            raise InvoiceError("O valor da baixa deve ser positivo")
        if value > invoice.open_amount:
            raise InvoiceError("O valor da baixa nao pode exceder o saldo em aberto")

        if invoice.kind is InvoiceKind.RECEIVABLE:
            control = self._account(DEFAULT_RECEIVABLE_CODE)
            splits = [Split(cash_account, value), Split(control, -value)]
        else:
            control = self._account(DEFAULT_PAYABLE_CODE)
            splits = [Split(control, value), Split(cash_account, -value)]

        transaction = Transaction(
            date=settlement_date,
            description=f"Baixa - {invoice.party_name() or invoice.description}",
            splits=splits,
        )
        self.ledger.post(transaction)

        settlement = Settlement(
            date=settlement_date,
            amount=value,
            transaction_id=transaction.id,
        )
        self.repo.add_settlement(invoice, settlement)
        invoice.settlements.append(settlement)
        return invoice

    # --------------------------------------------------------------- consultas
    def invoices(self) -> list[Invoice]:
        return self.repo.list_invoices()

    def open_invoices(self, kind: InvoiceKind | None = None) -> list[Invoice]:
        open_items = [
            invoice for invoice in self.invoices() if invoice.status is not InvoiceStatus.SETTLED
        ]
        if kind is not None:
            open_items = [invoice for invoice in open_items if invoice.kind is kind]
        return open_items

    def _account(self, code: str) -> Account:
        account = self.repo.get_account_by_code(code)
        if account is None:
            raise InvoiceError(f"Conta padrao nao encontrada: {code}")
        return account
