from datetime import date

from gnc_lite.domain.money import Money, money
from gnc_lite.domain.transaction import Split, Transaction
from gnc_lite.services import reports


def _post(ledger, day, description, splits_spec):
    splits = [
        Split(ledger.repo.get_account_by_code(code), money(value))
        for code, value in splits_spec
    ]
    ledger.post(
        Transaction(
            date=date(2026, 5, day),
            description=description,
            splits=splits,
        )
    )


def _sample_book(ledger):
    ledger.seed_default_chart()
    _post(ledger, 1, "Aporte do socio", [("1.1", "1000.00"), ("3.1", "-1000.00")])
    _post(ledger, 2, "Emprestimo recebido", [("1.1", "500.00"), ("2.2", "-500.00")])
    _post(ledger, 3, "Venda a vista", [("1.1", "300.00"), ("4.1", "-300.00")])
    _post(ledger, 4, "Pagamento de aluguel", [("5.3", "100.00"), ("1.1", "-100.00")])


def test_trial_balance_fecha(ledger):
    _sample_book(ledger)
    report = reports.trial_balance(ledger)
    total_debit, total_credit = report.footer[1], report.footer[2]
    assert total_debit == total_credit == money("1800.00")
    assert total_debit == money("1800.00")
    labels = [f"{row[0]}" for row in report.rows]
    assert any(label.startswith("1.1") for label in labels)
    assert any(label.startswith("5.3") for label in labels)


def test_dre_resultado(ledger):
    _sample_book(ledger)
    report = reports.income_statement(ledger)
    revenue_row = next(r for r in report.rows if isinstance(r[0], str) and r[0].startswith("4.1"))
    expense_row = next(r for r in report.rows if isinstance(r[0], str) and r[0].startswith("5.3"))
    assert revenue_row[1] == money("300.00")
    assert expense_row[1] == money("100.00")
    assert report.footer[1] == money("200.00")


def test_balanco_fecha(ledger):
    _sample_book(ledger)
    report = reports.balance_sheet(ledger)
    total_assets = next(r[1] for r in report.rows if r[0] == "Total do Ativo")
    liabilities_and_equity = next(
        r[1] for r in report.rows if r[0] == "Total do Passivo + Patrimonio Liquido"
    )
    assert total_assets == money("1700.00")
    assert total_assets == liabilities_and_equity


def test_fluxo_de_caixa(ledger):
    _sample_book(ledger)
    report = reports.cash_flow(ledger)
    footer = report.footer
    assert footer[0] == "TOTAIS"
    assert footer[1] == Money.zero()  # saldo inicial (livro comeca zerado)
    assert footer[2] == money("1800.00")  # entradas
    assert footer[3] == money("100.00")  # saidas
    assert footer[4] == money("1700.00")  # saldo final


def test_relatorios_com_periodo_filtram_datas(ledger):
    _sample_book(ledger)
    report = reports.income_statement(ledger, start=date(2026, 5, 1), end=date(2026, 5, 2))
    assert report.footer[1] == Money.zero()  # vendas/aluguel ocorreram nos dias 3 e 4