from datetime import date

import pytest

from gnc_lite.domain.invoice import InvoiceError, InvoiceKind, InvoiceStatus
from gnc_lite.domain.money import money
from gnc_lite.domain.party import PartyType
from gnc_lite.services import reports
from gnc_lite.services.billing import BillingService


@pytest.fixture
def billing(ledger):
    ledger.seed_default_chart()
    return BillingService(ledger)


def test_criar_parte(billing):
    cliente = billing.create_party("ACME Ltda", PartyType.CUSTOMER, document="00.000.000/0001-00")
    assert cliente.id is not None
    clientes = billing.parties(PartyType.CUSTOMER)
    assert [c.name for c in clientes] == ["ACME Ltda"]


def test_titulo_a_receber_emite_lancamento(billing, ledger):
    cliente = billing.create_party("ACME", PartyType.CUSTOMER)
    invoice = billing.issue_receivable(
        cliente,
        money("500.00"),
        date(2026, 6, 1),
        date(2026, 6, 30),
        description="Venda a prazo",
    )

    assert invoice.id is not None
    assert invoice.status is InvoiceStatus.OPEN
    assert invoice.open_amount == money("500.00")

    # contas a receber debitado, receita creditada
    ar = ledger.repo.get_account_by_code("1.3")
    vendas = ledger.repo.get_account_by_code("4.1")
    assert ledger.raw_balance(ar) == money("500.00")
    assert ledger.balance(vendas) == money("500.00")


def test_baixa_total_quita_titulo(billing, ledger):
    cliente = billing.create_party("ACME", PartyType.CUSTOMER)
    invoice = billing.issue_receivable(
        cliente, money("500.00"), date(2026, 6, 1), date(2026, 6, 30)
    )
    caixa = ledger.repo.get_account_by_code("1.1")
    billing.settle(invoice, date(2026, 6, 15), caixa)

    assert invoice.status is InvoiceStatus.SETTLED
    assert invoice.open_amount == money("0.00")
    ar = ledger.repo.get_account_by_code("1.3")
    assert ledger.raw_balance(ar) == money("0.00")
    assert ledger.raw_balance(caixa) == money("500.00")


def test_baixa_parcial(billing, ledger):
    cliente = billing.create_party("ACME", PartyType.CUSTOMER)
    invoice = billing.issue_receivable(
        cliente, money("500.00"), date(2026, 6, 1), date(2026, 6, 30)
    )
    caixa = ledger.repo.get_account_by_code("1.1")
    billing.settle(invoice, date(2026, 6, 15), caixa, money("200.00"))

    assert invoice.status is InvoiceStatus.PARTIAL
    assert invoice.open_amount == money("300.00")


def test_baixa_maior_que_saldo_falha(billing, ledger):
    cliente = billing.create_party("ACME", PartyType.CUSTOMER)
    invoice = billing.issue_receivable(
        cliente, money("500.00"), date(2026, 6, 1), date(2026, 6, 30)
    )
    caixa = ledger.repo.get_account_by_code("1.1")
    with pytest.raises(InvoiceError):
        billing.settle(invoice, date(2026, 6, 15), caixa, money("600.00"))


def test_titulo_a_pagar(billing, ledger):
    fornecedor = billing.create_party("Fornecedor XYZ", PartyType.VENDOR)
    invoice = billing.issue_payable(
        fornecedor,
        money("350.00"),
        date(2026, 7, 1),
        date(2026, 7, 10),
        description="Compra de material",
    )
    ap = ledger.repo.get_account_by_code("2.1")
    despesa = ledger.repo.get_account_by_code("5.1")
    assert ledger.balance(ap) == money("350.00")
    assert ledger.balance(despesa) == money("350.00")

    caixa = ledger.repo.get_account_by_code("1.1")
    billing.settle(invoice, date(2026, 7, 10), caixa)
    assert invoice.status is InvoiceStatus.SETTLED
    assert ledger.raw_balance(caixa) == money("-350.00")
    assert ledger.balance(ap) == money("0.00")


def test_relatorio_titulos_em_aberto(billing):
    cliente = billing.create_party("ACME", PartyType.CUSTOMER)
    fornecedor = billing.create_party("XYZ", PartyType.VENDOR)
    billing.issue_receivable(cliente, money("500.00"), date(2026, 6, 1), date(2026, 6, 30))
    invoice = billing.issue_receivable(
        cliente, money("100.00"), date(2026, 6, 1), date(2026, 6, 5)
    )
    billing.issue_payable(fornecedor, money("80.00"), date(2026, 6, 1), date(2026, 6, 20))
    caixa = billing.repo.get_account_by_code("1.1")
    billing.settle(invoice, date(2026, 6, 5), caixa)

    report = reports.open_items(billing)
    assert len(report.rows) == 2  # a receber 500 + a pagar 80 (a de 100 foi quitada)
    assert report.footer[5] == money("580.00")

    only_receivables = reports.open_items(billing, InvoiceKind.RECEIVABLE)
    assert len(only_receivables.rows) == 1
    assert only_receivables.title == "Contas a Receber"


def test_balancete_fecha_com_titulos(billing, ledger):
    cliente = billing.create_party("ACME", PartyType.CUSTOMER)
    invoice = billing.issue_receivable(
        cliente, money("500.00"), date(2026, 6, 1), date(2026, 6, 30)
    )
    caixa = ledger.repo.get_account_by_code("1.1")
    billing.settle(invoice, date(2026, 6, 15), caixa, money("200.00"))

    report = reports.trial_balance(ledger)
    assert report.footer[1] == report.footer[2]
