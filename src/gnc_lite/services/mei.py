"""Relatorio mensal e anual de faturamento do MEI (RMR).

Base legal: Resolucao CGSN n. 140/2018, art. 54 - o MEI deve manter relatorio
mensal das receitas brutas (RMR) contendo a identificacao do MEI (nome
empresarial, CNPJ e periodo), o registro das operacoes (data, valor, descricao
do produto/servico e identificacao do destinatario) e a separacao das receitas
de comercio/industria das de servicos.

A classificacao usa os codigos de conta: ``4.1`` (Vendas) = comercio/industria,
``4.2`` (Servicos) = servicos e demais contas de receita como "outras".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from gnc_lite.config import AppConfig
from gnc_lite.domain.account import AccountType
from gnc_lite.domain.money import Money
from gnc_lite.domain.transaction import Transaction
from gnc_lite.services.ledger import Ledger
from gnc_lite.services.reports import Report

COMMERCE_PREFIX = "4.1"
SERVICE_PREFIX = "4.2"

CATEGORY_COMMERCE = "comercio"
CATEGORY_SERVICES = "servicos"
CATEGORY_OTHER = "outras"

_MONTH_NAMES = [
    "Janeiro",
    "Fevereiro",
    "Marco",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]

_RMR_COLUMNS = [
    "N.",
    "Data",
    "Descricao do produto/servico",
    "Identificacao do destinatario",
    "Valor (R$)",
]


@dataclass
class RevenueEntry:
    """Uma receita (partida em conta de receita) do periodo."""

    day: date
    description: str
    party: str
    account_label: str
    category: str
    value: Money


def classify_code(code: str) -> str:
    """Categoria da conta de receita a partir do codigo."""
    if code.startswith(COMMERCE_PREFIX):
        return CATEGORY_COMMERCE
    if code.startswith(SERVICE_PREFIX):
        return CATEGORY_SERVICES
    return CATEGORY_OTHER


def effective_annual_limit(config: AppConfig, year: int) -> Money:
    """Limite anual aplicavel, proporcional no ano de inicio de atividade."""
    base = config.mei_limite_anual
    inicio = config.mei_inicio_atividade
    if inicio is not None and inicio.year == year:
        months = 12 - inicio.month + 1
        prorated = (Decimal(base.minor_units) * Decimal(months) / Decimal(12)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        return Money(int(prorated), base.currency)
    return base


def revenue_entries(
    ledger: Ledger,
    start: date,
    end: date,
    document_by_transaction: dict[int, str] | None = None,
) -> list[RevenueEntry]:
    """Coleta as receitas (creditos em contas de receita) no intervalo."""
    documents = document_by_transaction or {}
    entries: list[RevenueEntry] = []
    for transaction in ledger.transactions():
        if transaction.date < start or transaction.date > end:
            continue
        for split in transaction.splits:
            account = split.account
            if account is None or account.placeholder or account.type is not AccountType.INCOME:
                continue
            value = account.natural_balance(split.amount)
            if value.is_zero:
                continue
            entries.append(
                RevenueEntry(
                    day=transaction.date,
                    description=_description(transaction),
                    party=_buyer_label(transaction, documents),
                    account_label=f"{account.code} - {account.name}",
                    category=classify_code(account.code),
                    value=value,
                )
            )
    entries.sort(key=lambda entry: (entry.day, entry.account_label))
    return entries


def _description(transaction: Transaction) -> str:
    return transaction.description or transaction.memo or "(sem descricao)"


def _buyer_label(transaction: Transaction, documents: dict[int, str]) -> str:
    base = transaction.payee or ""
    document = documents.get(transaction.id) if transaction.id is not None else None
    if base and document:
        return f"{base} - {document}"
    return base or document or "(destinatario nao identificado)"


def document_map(ledger: Ledger) -> dict[int, str]:
    """Mapa transacao -> documento (CPF/CNPJ) do comprador, via titulos."""
    result: dict[int, str] = {}
    for invoice in ledger.repo.list_invoices():
        if invoice.transaction_id is None or invoice.party is None:
            continue
        if invoice.party.document:
            result[invoice.transaction_id] = invoice.party.document
    return result


def _sum_values(entries: list[RevenueEntry], category: str | None = None) -> Money:
    total = Money.zero()
    for entry in entries:
        if category is None or entry.category == category:
            total = total + entry.value
    return total


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (month // 12), (month % 12) + 1, 1)
    end = date.fromordinal(end.toordinal() - 1)
    return start, end


def _numbered_rows(entries: list[RevenueEntry]) -> list[tuple[object, ...]]:
    return [
        (
            str(index),
            entry.day.strftime("%d/%m/%Y"),
            entry.description,
            entry.party,
            entry.value,
        )
        for index, entry in enumerate(entries, start=1)
    ]


def _percent_text(part: Money, whole: Money) -> str:
    if whole.minor_units == 0:
        return "-"
    pct = Decimal(part.minor_units) / Decimal(whole.minor_units) * 100
    return f"{pct:.1f}".replace(".", ",") + "%"


def _brl(money: Money) -> str:
    return f"R$ {money.amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _company_info(config: AppConfig) -> list[tuple[str, str]]:
    info: list[tuple[str, str]] = [
        ("Nome empresarial", config.mei_nome_empresarial or "-"),
        ("CNPJ", config.mei_cnpj or "-"),
    ]
    if config.mei_atividade:
        info.append(("Atividade", config.mei_atividade))
    municipio = " ".join(part for part in (config.mei_municipio, config.mei_uf) if part).strip()
    if municipio:
        info.append(("Municipio/UF", municipio))
    if config.mei_inicio_atividade is not None:
        info.append(("Inicio de atividade", config.mei_inicio_atividade.strftime("%d/%m/%Y")))
    return info


def _limit_rows(total: Money, limit: Money) -> list[tuple[object, ...]]:
    return [
        ("Limite anual aplicavel", "", "", _brl(limit)),
        ("Percentual do limite utilizado", "", "", _percent_text(total, limit)),
        ("Situacao", "", "", _status_text(total, limit)),
    ]


def billing_report(ledger: Ledger, config: AppConfig, year: int, month: int) -> Report:
    """Relatorio Mensal das Receitas Brutas (RMR) no modelo oficial."""
    start, end = _month_bounds(year, month)
    documents = document_map(ledger)
    entries = revenue_entries(ledger, start, end, documents)

    commerce = [entry for entry in entries if entry.category == CATEGORY_COMMERCE]
    services = [entry for entry in entries if entry.category == CATEGORY_SERVICES]
    others = [entry for entry in entries if entry.category == CATEGORY_OTHER]

    subtotal_commerce = _sum_values(commerce)
    subtotal_services = _sum_values(services)
    subtotal_others = _sum_values(others)
    month_total = subtotal_commerce + subtotal_services

    rows: list[tuple[object, ...]] = []
    rows.append(("1. RECEITAS DE COMERCIO E INDUSTRIA", None, None, None, None))
    rows.extend(_numbered_rows(commerce))
    rows.append(("Total de Comercio e Industria", "", "", "", subtotal_commerce))
    rows.append(("2. RECEITAS DE SERVICOS", None, None, None, None))
    rows.extend(_numbered_rows(services))
    rows.append(("Total de Servicos", "", "", "", subtotal_services))

    notes = [
        "O presente relatorio e o documento comprobatorio das receitas brutas "
        "do mes, conforme o art. 54 da Resolucao CGSN n. 140/2018.",
        "Local e data: ____________________, ____/____/______   Assinatura: ____________________",
    ]
    if not subtotal_others.is_zero:
        notes.append(
            "Outras receitas do periodo (nao integram a receita bruta do MEI): "
            f"{_brl(subtotal_others)}"
        )

    footer = ("RECEITA BRUTA TOTAL DO MES", "", "", "", month_total)
    info = [*_company_info(config), ("Periodo", f"{month:02d}/{year}")]
    return Report(
        f"Relatorio Mensal das Receitas Brutas - {month:02d}/{year}",
        _RMR_COLUMNS,
        rows,
        footer,
        "",
        info=info,
        notes=notes,
    )


def annual_report(ledger: Ledger, config: AppConfig, year: int) -> Report:
    """Relatorio anual de faturamento do MEI (resumo mes a mes)."""
    documents = document_map(ledger)
    rows: list[tuple[object, ...]] = []
    year_commerce = Money.zero()
    year_services = Money.zero()
    for month in range(1, 13):
        start, end = _month_bounds(year, month)
        entries = revenue_entries(ledger, start, end, documents)
        commerce = _sum_values(entries, CATEGORY_COMMERCE)
        services = _sum_values(entries, CATEGORY_SERVICES)
        year_commerce = year_commerce + commerce
        year_services = year_services + services
        rows.append((_MONTH_NAMES[month - 1], commerce, services, commerce + services))
    year_total = year_commerce + year_services
    rows.append(("TOTAL DO ANO", year_commerce, year_services, year_total))

    limit = effective_annual_limit(config, year)
    info = [*_company_info(config), ("Ano", str(year))]
    info.extend((label, value) for label, _, _, value in _limit_rows(year_total, limit))

    footer = ("RECEITA BRUTA TOTAL DO ANO", "", "", year_total)
    return Report(
        f"Relatorio Anual das Receitas Brutas - {year}",
        ["Mes", "Comercio e Industria (R$)", "Servicos (R$)", "Total (R$)"],
        rows,
        footer,
        "",
        info=info,
        notes=[
            "Comercio/industria (conta 4.1) somado a servicos (conta 4.2) "
            "compoe a receita bruta anual do MEI.",
            "Limite anual de faturamento proporcional ao inicio de atividade, quando aplicavel.",
        ],
    )


def _status_text(ytd_total: Money, limit: Money) -> str:
    if limit.minor_units <= 0:
        return "Limite nao definido"
    if ytd_total > limit:
        return "Limite excedido"
    return "Dentro do limite"
