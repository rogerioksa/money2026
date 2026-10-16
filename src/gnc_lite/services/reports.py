"""Relatorios contabeis: balancete, DRE, balanco patrimonial e fluxo de caixa."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from gnc_lite.domain.account import Account, AccountType
from gnc_lite.domain.money import Money
from gnc_lite.services.ledger import Ledger


@dataclass
class Report:
    """Relatorio simples: titulo, colunas, linhas e rodape de totais.

    ``info`` e uma lista de pares (rotulo, valor) exibida como cabecalho
    (identificacao do documento). ``notes`` sao observacoes de rodape.
    """

    title: str
    columns: list[str]
    rows: list[tuple[object, ...]]
    footer: tuple[object, ...] | None = None
    period: str = ""
    info: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def period_label(start: date | None, end: date | None) -> str:
    if start is None and end is None:
        return "Periodo: integral (todo o livro)"
    start_text = start.strftime("%d/%m/%Y") if start else "inicio"
    end_text = end.strftime("%d/%m/%Y") if end else "hoje"
    return f"Periodo: {start_text} a {end_text}"


# ---------------------------------------------------------------- balancete
def trial_balance(ledger: Ledger) -> Report:
    """Balancete de verificacao: debitos contra creditos de cada conta."""
    rows: list[tuple[object, ...]] = []
    total_debit = Money.zero()
    total_credit = Money.zero()

    for account in ledger.list_accounts():
        if account.placeholder:
            continue
        raw = ledger.raw_balance(account)
        if raw.is_zero:
            continue
        debit = raw if raw.minor_units > 0 else Money.zero()
        credit = -raw if raw.minor_units < 0 else Money.zero()
        total_debit += debit
        total_credit += credit
        rows.append((f"{account.code} - {account.name}", debit, credit))

    rows.sort(key=lambda row: str(row[0]))
    footer = ("TOTAIS", total_debit, total_credit)
    return Report(
        "Balancete de Verificacao",
        ["Conta", "Debito", "Credito"],
        rows,
        footer,
        period_label(None, None),
    )


# ----------------------------------------------------------------------- DRE
def income_statement(
    ledger: Ledger,
    start: date | None = None,
    end: date | None = None,
) -> Report:
    """Demonstracao do Resultado: receitas, despesas e resultado do periodo."""
    revenues = _rows_for_type(ledger, AccountType.INCOME, start, end)
    expenses = _rows_for_type(ledger, AccountType.EXPENSE, start, end)
    total_revenue = _sum_rows(revenues)
    total_expense = _sum_rows(expenses)
    net_income = total_revenue - total_expense

    rows: list[tuple[object, ...]] = [
        ("RECEITAS", None),
        *revenues,
        ("Total de Receitas", total_revenue),
        ("DESPESAS", None),
        *expenses,
        ("Total de Despesas", total_expense),
    ]
    footer = ("Resultado do Periodo (Lucro/Prejuizo)", net_income)
    return Report(
        "Demonstracao do Resultado (DRE)",
        ["Conta", "Valor"],
        rows,
        footer,
        period_label(start, end),
    )


# -------------------------------------------------------------------- balanco
def balance_sheet(ledger: Ledger, asof: date | None = None) -> Report:
    """Balanco patrimonial na data de referencia."""
    assets = _rows_for_type(ledger, AccountType.ASSET, None, asof)
    liabilities = _rows_for_type(ledger, AccountType.LIABILITY, None, asof)
    equity = _rows_for_type(ledger, AccountType.EQUITY, None, asof)

    total_assets = _sum_rows(assets)
    total_liabilities = _sum_rows(liabilities)
    total_equity = _sum_rows(equity)
    net_income = _net_income(ledger, None, asof)
    liabilities_and_equity = total_liabilities + total_equity + net_income

    rows: list[tuple[object, ...]] = [
        ("ATIVO", None),
        *assets,
        ("Total do Ativo", total_assets),
        ("PASSIVO", None),
        *liabilities,
        ("Total do Passivo", total_liabilities),
        ("PATRIMONIO LIQUIDO", None),
        *equity,
        ("Lucro/Prejuizo do Periodo", net_income),
        ("Total do Passivo + Patrimonio Liquido", liabilities_and_equity),
    ]
    footer = ("Total do Ativo x Total Passivo + PL", total_assets)
    return Report(
        "Balanco Patrimonial",
        ["Conta", "Valor"],
        rows,
        footer,
        period_label(None, asof),
    )


# --------------------------------------------------------------- fluxo caixa
def cash_flow(
    ledger: Ledger,
    start: date | None = None,
    end: date | None = None,
) -> Report:
    """Fluxo de caixa: saldos inicial/final e movimentacao das contas de caixa."""
    rows: list[tuple[object, ...]] = []
    total_opening = Money.zero()
    total_inflows = Money.zero()
    total_outflows = Money.zero()
    total_closing = Money.zero()

    day_before_start = start - timedelta(days=1) if start is not None else None
    for account in ledger.list_accounts():
        if account.placeholder or not _is_cash(account):
            continue
        if start is not None and day_before_start is not None:
            opening = ledger.raw_balance_asof(account, day_before_start)
        else:
            opening = Money.zero(account.currency)
        inflows, outflows = ledger.movements(account, start, end)
        closing = opening + inflows - outflows

        total_opening += opening
        total_inflows += inflows
        total_outflows += outflows
        total_closing += closing
        rows.append(
            (
                f"{account.code} - {account.name}",
                opening,
                inflows,
                outflows,
                closing,
            )
        )

    footer = ("TOTAIS", total_opening, total_inflows, total_outflows, total_closing)
    return Report(
        "Fluxo de Caixa",
        ["Conta", "Saldo inicial", "Entradas", "Saidas", "Saldo final"],
        rows,
        footer,
        period_label(start, end),
    )


# ------------------------------------------------------------------- apoio
def _rows_for_type(
    ledger: Ledger,
    account_type: AccountType,
    start: date | None,
    end: date | None,
) -> list[tuple[str, Money]]:
    rows: list[tuple[str, Money]] = []
    for account in ledger.list_accounts():
        if account.type is not account_type or account.placeholder:
            continue
        balance = ledger.balance_in_range(account, start, end)
        if not balance.is_zero:
            rows.append((f"{account.code} - {account.name}", balance))
    return rows


def _sum_rows(rows: list[tuple[str, Money]]) -> Money:
    total = Money.zero()
    for _, amount in rows:
        total = total + amount
    return total


def _net_income(
    ledger: Ledger,
    start: date | None,
    end: date | None,
) -> Money:
    revenues = _sum_rows(_rows_for_type(ledger, AccountType.INCOME, start, end))
    expenses = _sum_rows(_rows_for_type(ledger, AccountType.EXPENSE, start, end))
    return revenues - expenses


def _is_cash(account: Account) -> bool:
    return account.code.startswith("1.1") or account.code.startswith("1.2")


# -------------------------------------------------------------- titulos
def open_items(billing, kind=None, asof: date | None = None) -> Report:  # noqa: ANN001
    """Lista os titulos a receber/pagar ainda em aberto."""
    from gnc_lite.domain.invoice import InvoiceKind

    reference = asof or date.today()
    rows: list[tuple[object, ...]] = []
    total_amount = Money.zero()
    total_open = Money.zero()

    for invoice in billing.open_invoices(kind):
        overdue = invoice.is_overdue(reference)
        situation = invoice.status.label + (" (vencido)" if overdue else "")
        rows.append(
            (
                invoice.kind.label,
                invoice.party_name(),
                invoice.due_date.strftime("%d/%m/%Y"),
                situation,
                invoice.amount,
                invoice.open_amount,
            )
        )
        total_amount += invoice.amount
        total_open += invoice.open_amount

    rows.sort(key=lambda row: str(row[2]))
    footer = ("TOTAIS", "", "", "", total_amount, total_open)
    title = "Titulos em Aberto"
    if kind is InvoiceKind.RECEIVABLE:
        title = "Contas a Receber"
    elif kind is InvoiceKind.PAYABLE:
        title = "Contas a Pagar"
    return Report(
        title,
        ["Tipo", "Parte", "Vencimento", "Situacao", "Valor", "Em aberto"],
        rows,
        footer,
    )
