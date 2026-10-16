from datetime import date

import pytest

from gnc_lite.db.repository import Repository
from gnc_lite.db.session import connect, init_db, make_session
from gnc_lite.domain.money import money
from gnc_lite.domain.transaction import Split, Transaction
from gnc_lite.services import exporter, importer
from gnc_lite.services.ledger import Ledger


@pytest.fixture
def fresh_ledger():
    engine = connect(":memory:")
    init_db(engine)
    session = make_session(engine)()
    book = Ledger(Repository(session))
    book.seed_default_chart()
    session.commit()
    return book


def _sample(ledger):
    caixa = ledger.repo.get_account_by_code("1.1")
    vendas = ledger.repo.get_account_by_code("4.1")
    aluguel = ledger.repo.get_account_by_code("5.3")
    ledger.post(
        Transaction(
            date=date(2026, 4, 1),
            description="Venda a vista",
            payee="Cliente A",
            splits=[Split(caixa, money("300.00")), Split(vendas, money("-300.00"))],
        )
    )
    ledger.post(
        Transaction(
            date=date(2026, 4, 2),
            description="Pagamento de aluguel",
            splits=[Split(aluguel, money("100.00")), Split(caixa, money("-100.00"))],
        )
    )


def test_csv_round_trip(fresh_ledger):
    _sample(fresh_ledger)
    csv_text = exporter.transactions_to_csv(fresh_ledger)

    target = Ledger(Repository(make_session(connect(":memory:"))()))
    init_db(target.repo.session.get_bind())
    target.seed_default_chart()
    target.repo.session.commit()

    transactions = importer.read_transactions_csv(target, csv_text)
    assert len(transactions) == 2
    target.post_many(transactions)

    caixa = target.repo.get_account_by_code("1.1")
    vendas = target.repo.get_account_by_code("4.1")
    assert target.raw_balance(caixa) == money("200.00")
    assert target.balance(vendas) == money("300.00")


def test_csv_colunas_obrigatorias(fresh_ledger):
    with pytest.raises(importer.ImportParseError):
        importer.read_transactions_csv(fresh_ledger, "date,description\n2026-01-01,x\n")


def test_importar_qif(fresh_ledger):
    caixa = fresh_ledger.repo.get_account_by_code("1.1")
    qif = (
        "!Type:Bank\n"
        "D04/05/2026\n"
        "T250.00\n"
        "PCliente QIF\n"
        "L4.1\n"
        "MVenda importada\n"
        "^\n"
        "D04/06/2026\n"
        "T-80.00\n"
        "PEmpresa de Luz\n"
        "L5.4\n"
        "^\n"
    )
    transactions = importer.read_qif(fresh_ledger, qif, caixa)
    assert len(transactions) == 2
    fresh_ledger.post_many(transactions)

    vendas = fresh_ledger.repo.get_account_by_code("4.1")
    despesas = fresh_ledger.repo.get_account_by_code("5.4")
    assert fresh_ledger.balance(vendas) == money("250.00")
    assert fresh_ledger.balance(despesas) == money("80.00")
    assert fresh_ledger.raw_balance(caixa) == money("170.00")


def test_importar_ofx(fresh_ledger):
    caixa = fresh_ledger.repo.get_account_by_code("1.1")
    contrapartida = fresh_ledger.repo.get_account_by_code("4.1")
    ofx = """<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>
    <STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260420<TRNAMT>420.50
    <FITID>1<NAME>Recebimento OFX<MEMO>Nota 123</STMTTRN>
    </STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""
    transactions = importer.read_ofx(fresh_ledger, ofx, caixa, contrapartida)
    assert len(transactions) == 1
    assert transactions[0].date == date(2026, 4, 20)
    fresh_ledger.post_many(transactions)
    assert fresh_ledger.raw_balance(caixa) == money("420.50")


def test_report_to_html(fresh_ledger):
    _sample(fresh_ledger)
    from gnc_lite.services import reports

    html = exporter.report_to_html(reports.trial_balance(fresh_ledger))
    assert "<table" in html
    assert "Balancete" in html
    assert "300,00" in html


def test_exportar_pdf_reportlab(fresh_ledger, tmp_path):
    from gnc_lite.services import reports

    report = reports.trial_balance(fresh_ledger)
    target = tmp_path / "balancete.pdf"
    exporter.write_report_pdf(report, target)
    assert target.exists()
    assert target.stat().st_size > 0
