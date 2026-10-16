"""Ledger: operacoes de contabilidade sobre o repositorio."""

from __future__ import annotations

from datetime import date

from gnc_lite.db.chart import CHART_BUSINESS, seed_default_chart
from gnc_lite.db.repository import Repository
from gnc_lite.domain.account import ACCOUNT_KIND_NORMAL, Account, AccountType
from gnc_lite.domain.money import DEFAULT_CURRENCY, Money
from gnc_lite.domain.transaction import Transaction


class Ledger:
    """Fachada para criar contas, lancar transacoes e consultar saldos."""

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    # ----------------------------------------------------------------- contas
    def create_account(
        self,
        code: str,
        name: str,
        type: AccountType,
        *,
        parent: Account | None = None,
        currency: str = DEFAULT_CURRENCY,
        description: str = "",
        placeholder: bool = False,
        kind: str = ACCOUNT_KIND_NORMAL,
        credit_limit_minor: int = 0,
    ) -> Account:
        account = Account(
            code=code,
            name=name,
            type=type,
            currency=currency,
            description=description,
            placeholder=placeholder,
            parent=parent,
            kind=kind,
            credit_limit_minor=credit_limit_minor,
        )
        return self.repo.add_account(account)

    def list_accounts(self) -> list[Account]:
        return self.repo.list_accounts()

    def seed_default_chart(self, chart: str = CHART_BUSINESS) -> list[Account]:
        return seed_default_chart(self.repo, chart)

    def update_account(self, account: Account) -> Account:
        """Persiste nome/descricao/agrupadora de uma conta existente."""
        return self.repo.update_account(account)

    def has_postings(self, account: Account) -> bool:
        """Se a conta ja tem partidas lancadas."""
        if account.id is None:
            return False
        return self.repo.has_postings(account.id)

    # ------------------------------------------------------------ lancamentos
    def post(self, transaction: Transaction) -> Transaction:
        """Persiste um lancamento balanceado."""
        return self.repo.add_transaction(transaction)

    def post_many(self, transactions: list[Transaction]) -> list[Transaction]:
        """Persiste varios lancamentos em sequencia."""
        return [self.repo.add_transaction(transaction) for transaction in transactions]

    def transactions(self) -> list[Transaction]:
        return self.repo.list_transactions()

    # ----------------------------------------------------------------- saldos
    def raw_balance(self, account: Account) -> Money:
        """Saldo bruto (debitos positivos, creditos negativos), com descendentes."""
        return self.raw_balance_in_range(account)

    def raw_balance_in_range(
        self,
        account: Account,
        start: date | None = None,
        end: date | None = None,
    ) -> Money:
        """Saldo bruto entre datas (toda a serie quando as datas sao None)."""
        ids = self._ids_with_descendants(account)
        total = self.repo.sum_minor_units_between(ids, start, end)
        return Money(total, account.currency)

    def raw_balance_asof(self, account: Account, asof: date | None) -> Money:
        """Saldo bruto ate uma data (inclusive)."""
        if asof is None:
            return self.raw_balance(account)
        return self.raw_balance_in_range(account, None, asof)

    def balance(self, account: Account) -> Money:
        """Saldo no sentido natural da conta."""
        return self.balance_in_range(account)

    def balance_in_range(
        self,
        account: Account,
        start: date | None = None,
        end: date | None = None,
    ) -> Money:
        """Saldo no sentido natural da conta, entre datas."""
        return account.natural_balance(self.raw_balance_in_range(account, start, end))

    def movements(
        self,
        account: Account,
        start: date | None = None,
        end: date | None = None,
    ) -> tuple[Money, Money]:
        """Debitos e creditos brutos do periodo, como valores positivos."""
        ids = self._ids_with_descendants(account)
        debits, credits = self.repo.debit_credit_between(ids, start, end)
        return Money(debits, account.currency), Money(credits, account.currency)

    # ------------------------------------------------------------------ apoio
    def _ids_with_descendants(self, account: Account) -> list[int]:
        if account.id is None:
            return []
        accounts = self.repo.list_accounts()
        children: dict[int, list[int]] = {}
        for acc in accounts:
            if acc.parent is not None and acc.parent.id is not None:
                children.setdefault(acc.parent.id, []).append(acc.id)  # type: ignore[arg-type]

        collected: list[int] = []
        stack = [account.id]
        while stack:
            current = stack.pop()
            collected.append(current)
            stack.extend(children.get(current, []))
        return collected
