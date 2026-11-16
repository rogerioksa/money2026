"""Painel: indicadores do mês e sugestões priorizadas."""

from __future__ import annotations

from datetime import date, timedelta

from money99.db.repository import Repository
from money99.db.session import connect, init_db, make_session
from money99.domain.account import Account
from money99.domain.title import Title
from money99.domain.transaction import Transaction
from money99.services.insights import dashboard_insights


def setup_repo(tmp_path):
    engine = connect(tmp_path / "insights.sqlite")
    init_db(engine)
    return Repository(make_session(engine))


def add_txn(repo, account_id, amount, category_id=None, day="2026-05-10"):
    return repo.add_transaction(Transaction(
        date=day,
        account_id=account_id,
        amount=amount,
        category_id=category_id,
    ))


def test_month_flow_and_savings_rate(tmp_path):
    repo = setup_repo(tmp_path)
    account = repo.add_account(Account(name="BANCO", type="bank", initial_balance=0))
    cats = {c.name: c for c in repo.list_categories()}
    add_txn(repo, account.id, 100000, cats["SALÁRIO"].id, "2026-05-02")
    add_txn(repo, account.id, -25000, cats["ALIMENTAÇÃO"].id)
    add_txn(repo, account.id, -15000, cats["TRANSPORTE"].id)

    flow = dashboard_insights(repo, 2026, 5)["flow"]
    assert flow["income"] == 100000
    assert flow["expense"] == 40000
    assert flow["result"] == 60000
    assert flow["savings_rate"] == 60
    assert flow["expense_change"] is None  # sem base no mês anterior


def test_month_flow_ignores_transfers(tmp_path):
    repo = setup_repo(tmp_path)
    bank = repo.add_account(Account(name="BANCO", type="bank", initial_balance=0))
    wallet = repo.add_account(Account(name="Carteira", type="cash", initial_balance=0))
    repo.add_transaction(Transaction(
        date="2026-05-05",
        account_id=bank.id,
        amount=-10000,
        transfer_account_id=wallet.id,
    ))

    flow = dashboard_insights(repo, 2026, 5)["flow"]
    assert flow["income"] == 0
    assert flow["expense"] == 0
    assert flow["savings_rate"] is None


def test_title_indicators_and_overdue_suggestion(tmp_path):
    repo = setup_repo(tmp_path)
    repo.add_account(Account(name="BANCO", type="bank", initial_balance=0))
    today = date.today()
    repo.add_title(Title(
        type="payable",
        description="ALUGUEL",
        amount=120000,
        due_date=(today - timedelta(days=3)).isoformat(),
    ))
    repo.add_title(Title(
        type="receivable",
        description="CLIENTE",
        amount=80000,
        due_date=(today + timedelta(days=2)).isoformat(),
    ))

    data = dashboard_insights(repo, today.year, today.month)
    titles = data["titles"]
    assert titles["payable_open"] == 120000
    assert titles["receivable_open"] == 80000
    assert titles["overdue_count"] == 1
    assert titles["upcoming_count"] == 1
    assert any(
        s["level"] == "danger" and "vencido" in s["title"]
        for s in data["suggestions"]
    )
    assert any("vence em 7 dias" in s["title"] for s in data["suggestions"])


def test_partial_title_uses_remaining_amount(tmp_path):
    repo = setup_repo(tmp_path)
    repo.add_account(Account(name="BANCO", type="bank", initial_balance=0))
    today = date.today()
    repo.add_title(Title(
        type="payable",
        description="CARRO",
        amount=100000,
        due_date=(today + timedelta(days=20)).isoformat(),
        status="partial",
        paid_amount=30000,
    ))

    titles = dashboard_insights(repo, today.year, today.month)["titles"]
    assert titles["payable_open"] == 70000
    assert titles["payable_count"] == 1


def test_budget_overrun_suggestion(tmp_path):
    repo = setup_repo(tmp_path)
    account = repo.add_account(Account(name="BANCO", type="bank", initial_balance=0))
    cats = {c.name: c for c in repo.list_categories()}
    repo.set_annual_budget(2026, cats["ALIMENTAÇÃO"].id, 12000)
    add_txn(repo, account.id, -20000, cats["ALIMENTAÇÃO"].id)

    data = dashboard_insights(repo, 2026, 5)
    suggestion = next(s for s in data["suggestions"] if "orçamento" in s["title"])
    assert suggestion["level"] in ("warning", "danger")
    assert "ALIMENTAÇÃO" in suggestion["detail"]


def test_category_increase_detected(tmp_path):
    repo = setup_repo(tmp_path)
    account = repo.add_account(Account(name="BANCO", type="bank", initial_balance=0))
    cats = {c.name: c for c in repo.list_categories()}
    add_txn(repo, account.id, -5000, cats["ALIMENTAÇÃO"].id, "2026-04-10")
    add_txn(repo, account.id, -15000, cats["ALIMENTAÇÃO"].id, "2026-05-10")

    data = dashboard_insights(repo, 2026, 5)
    row = next(r for r in data["category_increases"] if r["category"] == "ALIMENTAÇÃO")
    assert row["current"] == 15000
    assert row["previous"] == 5000
    assert row["change"] == 200
    assert any(s["title"] == "Gastos em alta" for s in data["suggestions"])


def test_credit_usage_suggestion(tmp_path):
    repo = setup_repo(tmp_path)
    repo.add_account(Account(
        name="Cartão",
        type="credit",
        credit_limit=100000,
        initial_balance=-95000,
    ))

    data = dashboard_insights(repo, 2026, 5)
    assert data["credit"]["used_pct"] == 95
    assert any(
        s["title"] == "Crédito quase esgotado"
        for s in data["suggestions"]
    )


def test_uncategorized_transactions_suggestion(tmp_path):
    repo = setup_repo(tmp_path)
    account = repo.add_account(Account(name="BANCO", type="bank", initial_balance=0))
    add_txn(repo, account.id, -7000)

    data = dashboard_insights(repo, 2026, 5)
    assert data["flow"]["uncategorized_count"] == 1
    assert data["flow"]["uncategorized_amount"] == 7000
    assert any("sem categoria" in s["title"] for s in data["suggestions"])


def test_dashboard_api_includes_insights(client):
    client.post("/api/accounts", json={
        "name": "BANCO", "type": "bank", "initial_balance": 0,
    })

    res = client.get("/api/reports/dashboard?year=2026&month=5")
    assert res.status_code == 200
    body = res.get_json()
    assert body["year"] == 2026
    assert body["month"] == 5
    assert "flow" in body
    assert "titles" in body
    assert "future" in body
    assert "suggestions" in body
    assert "used_pct" in body["credit"]
    assert "accounts" in body["credit"]

    # Ano/mês inválidos caem no período atual sem quebrar o painel.
    assert client.get("/api/reports/dashboard?year=2026&month=13").status_code == 200
