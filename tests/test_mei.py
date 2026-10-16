from datetime import date

import pytest

from gnc_lite.config import AppConfig, Profile
from gnc_lite.db.repository import Repository
from gnc_lite.db.session import connect, init_db, make_session
from gnc_lite.domain.money import Money
from gnc_lite.domain.party import PartyType
from gnc_lite.domain.transaction import Split, Transaction
from gnc_lite.services import mei
from gnc_lite.services.billing import BillingService
from gnc_lite.services.ledger import Ledger


@pytest.fixture
def ledger():
    engine = connect(":memory:")
    init_db(engine)
    session = make_session(engine)()
    book = Ledger(Repository(session))
    book.seed_default_chart()
    session.commit()
    return book


def post_income(book, day, code, amount, description, payee=""):
    cash = book.repo.get_account_by_code("1.1")
    income = book.repo.get_account_by_code(code)
    value = Money.from_decimal(amount)
    book.post(
        Transaction(
            date=day,
            description=description,
            payee=payee,
            splits=[Split(cash, value), Split(income, -value)],
        )
    )


def row_value(report, label):
    for row in report.rows:
        if row[0] == label:
            return row[-1]
    raise AssertionError(label)


def info_value(report, label):
    for key, value in report.info:
        if key == label:
            return value
    raise AssertionError(label)


def detail_text(report, column=3):
    return " ".join(str(row[column]) for row in report.rows if len(row) > column)


def test_classify_code():
    assert mei.classify_code("4.1") == mei.CATEGORY_COMMERCE
    assert mei.classify_code("4.1.2") == mei.CATEGORY_COMMERCE
    assert mei.classify_code("4.2") == mei.CATEGORY_SERVICES
    assert mei.classify_code("4.3") == mei.CATEGORY_OTHER


def test_limite_proporcional_no_ano_de_abertura():
    config = AppConfig(profile=Profile.MEI, mei_inicio_atividade=date(2026, 7, 1))
    limit = mei.effective_annual_limit(config, 2026)
    assert limit == Money.from_decimal("40500.00")
    assert mei.effective_annual_limit(config, 2027) == Money.from_decimal("81000.00")


def test_relatorio_mensal_no_modelo_rmr(ledger):
    post_income(ledger, date(2026, 3, 5), "4.1", "1000.00", "Venda balcao", "Cliente A")
    post_income(ledger, date(2026, 3, 12), "4.2", "500.00", "Servico de entrega", "Empresa B")
    post_income(ledger, date(2026, 2, 20), "4.1", "300.00", "Venda fevereiro")
    post_income(ledger, date(2026, 3, 20), "4.3", "50.00", "Juros recebidos")

    config = AppConfig(
        profile=Profile.MEI,
        mei_limite_anual=Money.from_decimal("81000.00"),
        mei_nome_empresarial="Teste MEI",
        mei_cnpj="11.222.333/0001-44",
    )
    report = mei.billing_report(ledger, config, 2026, 3)

    assert "Relatorio Mensal das Receitas Brutas" in report.title
    assert ("1. RECEITAS DE COMERCIO E INDUSTRIA", None, None, None, None) in report.rows
    assert ("2. RECEITAS DE SERVICOS", None, None, None, None) in report.rows
    assert row_value(report, "Total de Comercio e Industria") == Money.from_decimal("1000.00")
    assert row_value(report, "Total de Servicos") == Money.from_decimal("500.00")
    assert report.footer[0] == "RECEITA BRUTA TOTAL DO MES"
    assert report.footer[-1] == Money.from_decimal("1500.00")
    assert info_value(report, "CNPJ") == "11.222.333/0001-44"
    assert info_value(report, "Periodo") == "03/2026"
    assert "Cliente A" in detail_text(report)


def test_relatorio_usa_documento_do_comprador(ledger):
    billing = BillingService(ledger)
    party = billing.create_party("Empresa B", PartyType.CUSTOMER, document="11.222.333/0001-44")
    billing.issue_receivable(
        party,
        Money.from_decimal("800.00"),
        date(2026, 4, 1),
        date(2026, 4, 30),
        income_account=ledger.repo.get_account_by_code("4.2"),
    )
    ledger.repo.session.commit()

    config = AppConfig(profile=Profile.MEI)
    report = mei.billing_report(ledger, config, 2026, 4)
    assert "11.222.333/0001-44" in detail_text(report)


def test_relatorio_anual_resumo_e_situacao(ledger):
    post_income(ledger, date(2026, 3, 5), "4.1", "1000.00", "Venda balcao")
    post_income(ledger, date(2026, 3, 12), "4.2", "500.00", "Servico")
    post_income(ledger, date(2026, 5, 10), "4.1", "80000.00", "Venda grande")

    config = AppConfig(profile=Profile.MEI, mei_limite_anual=Money.from_decimal("81000.00"))
    report = mei.annual_report(ledger, config, 2026)

    assert "Relatorio Anual" in report.title
    assert row_value(report, "Marco") == Money.from_decimal("1500.00")
    assert row_value(report, "Maio") == Money.from_decimal("80000.00")
    assert row_value(report, "TOTAL DO ANO") == Money.from_decimal("81500.00")
    assert report.footer[-1] == Money.from_decimal("81500.00")
    assert info_value(report, "Situacao") == "Limite excedido"
