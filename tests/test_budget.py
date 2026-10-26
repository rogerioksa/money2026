"""Orçamentos: serviço (planejado x realizado) e API."""

from __future__ import annotations

from money99.db.repository import Repository
from money99.db.session import connect, init_db, make_session
from money99.domain.account import Account
from money99.domain.transaction import Transaction
from money99.services.budget import actual_by_category, budget_report


def setup_db(tmp_path):
    engine = connect(tmp_path / "b.sqlite")
    init_db(engine)
    return make_session(engine)


def test_actual_by_category_sums_expenses(tmp_path):
    session = setup_db(tmp_path)
    repo = Repository(session)
    account = repo.add_account(Account(name="Banco", type="bank"))
    cats = {c.name: c for c in repo.list_categories(kind="expense")}

    repo.add_transaction(Transaction(
        date="2026-10-05", account_id=account.id, amount=-3000,
        category_id=cats["Alimentação"].id,
    ))
    repo.add_transaction(Transaction(
        date="2026-10-15", account_id=account.id, amount=-2000,
        category_id=cats["Alimentação"].id,
    ))
    repo.add_transaction(Transaction(
        date="2026-11-01", account_id=account.id, amount=-5000,
        category_id=cats["Transporte"].id,
    ))
    session.commit()

    totals = actual_by_category(repo, 2026, 10)
    assert totals[cats["Alimentação"].id] == 5000
    assert cats["Transporte"].id not in totals


def test_budget_report(tmp_path):
    session = setup_db(tmp_path)
    repo = Repository(session)
    account = repo.add_account(Account(name="Banco", type="bank"))
    food = {c.name: c for c in repo.list_categories(kind="expense")}["Alimentação"]

    repo.set_annual_budget(2026, food.id, 96000)
    repo.add_transaction(Transaction(
        date="2026-10-05", account_id=account.id, amount=-5000, category_id=food.id,
    ))
    session.commit()

    report = budget_report(repo, 2026, 10)
    row = next(r for r in report if r["category_id"] == food.id)
    assert row["planned"] == 8000
    assert row["actual"] == 5000
    assert row["remaining"] == 3000


def test_budget_report_excludes_transfers(tmp_path):
    session = setup_db(tmp_path)
    repo = Repository(session)
    a = repo.add_account(Account(name="A", type="bank"))
    b = repo.add_account(Account(name="B", type="bank"))
    repo.add_transaction(Transaction(
        date="2026-10-05", account_id=a.id, amount=-1000, transfer_account_id=b.id,
    ))
    session.commit()
    assert budget_report(repo, 2026, 10) == []


def test_budget_api_roundtrip(client):
    cats = client.get("/api/categories?kind=expense").get_json()
    food = next(c for c in cats if c["name"] == "Alimentação")
    account = client.post("/api/accounts", json={"name": "Banco", "type": "bank"}).get_json()

    res = client.put("/api/budgets", json={
        "year": 2026, "category_id": food["id"], "annual_planned": 96000,
    })
    assert res.status_code == 200

    client.post("/api/transactions", json={
        "date": "2026-10-05", "account_id": account["id"], "amount": -5000,
        "category_id": food["id"],
    })

    res = client.get("/api/budgets?year=2026&month=10")
    assert res.status_code == 200
    row = next(r for r in res.get_json() if r["category_id"] == food["id"])
    assert row["category_id"] == food["id"]
    assert row["category"] == "Alimentação"
    assert row["planned"] == 8000
    assert row["actual"] == 5000
    assert row["remaining"] == 3000
    assert row["annual_planned"] == 96000


def test_budget_api_validation(client):
    assert client.get("/api/budgets").status_code == 400
    assert client.put("/api/budgets", json={
        "year": 2026, "month": 10, "category_id": 999, "planned": 100,
    }).status_code == 404
    assert client.put("/api/budgets", json={
        "year": 2026, "category_id": 1, "annual_planned": -5,
    }).status_code == 400
