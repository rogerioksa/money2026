"""Conciliação bancária: resumo e endpoint."""

from __future__ import annotations

from money99.db.repository import Repository
from money99.db.session import connect, init_db, make_session
from money99.domain.account import Account
from money99.domain.transaction import Transaction
from money99.services.reconcile import reconciliation_summary


def test_reconciliation_summary(client):
    account = client.post("/api/accounts", json={
        "name": "Banco", "type": "bank", "initial_balance": 20000,
    }).get_json()
    other = client.post("/api/accounts", json={"name": "Outra", "type": "bank"}).get_json()
    food = next(c for c in client.get("/api/categories?kind=expense").get_json()
                if c["name"] == "Alimentação")

    t1 = client.post("/api/transactions", json={
        "date": "2026-05-01", "account_id": account["id"], "amount": -5000,
        "category_id": food["id"],
    }).get_json()
    client.post("/api/transactions", json={
        "date": "2026-05-02", "account_id": account["id"], "amount": -3000,
        "category_id": food["id"],
    })
    # transferência recebida na conta principal
    client.post("/api/transactions", json={
        "date": "2026-05-03", "account_id": other["id"], "amount": -1000,
        "transfer_account_id": account["id"],
    })

    res = client.get(f"/api/accounts/{account['id']}/reconciliation")
    assert res.status_code == 200
    body = res.get_json()
    assert body["balance"] == 20000 - 5000 - 3000 + 1000
    assert body["reconciled_total"] == 0
    assert body["pending_count"] == 3
    assert body["difference"] == body["balance"]

    client.post(f"/api/transactions/{t1['id']}/reconcile", json={"reconciled": True})
    body = client.get(f"/api/accounts/{account['id']}/reconciliation").get_json()
    assert body["reconciled_total"] == -5000
    assert body["pending_count"] == 2
    assert body["difference"] == 20000 - 3000 + 1000


def test_reconciliation_unknown_account(client):
    assert client.get("/api/accounts/999/reconciliation").status_code == 404


def test_reconciliation_summary_service(tmp_path):
    engine = connect(tmp_path / "r.sqlite")
    init_db(engine)
    session = make_session(engine)
    repo = Repository(session)
    account = repo.add_account(Account(name="Banco", type="bank", initial_balance=10000))
    food = {c.name: c for c in repo.list_categories(kind="expense")}["Alimentação"]
    repo.add_transaction(Transaction(
        date="2026-05-01", account_id=account.id, amount=-2000, category_id=food.id,
    ))
    session.commit()

    summary = reconciliation_summary(repo, account.id)
    assert summary["balance"] == 8000
    assert summary["pending_count"] == 1
    assert summary["pending_total"] == -2000


def test_suggest_matches_groups_same_amount(client):
    account = client.post("/api/accounts", json={
        "name": "Banco", "type": "bank",
    }).get_json()
    food = next(c for c in client.get("/api/categories?kind=expense").get_json()
                if c["name"] == "Alimentação")
    # duas saídas idênticas em datas próximas (ex.: duplicata importada)
    client.post("/api/transactions", json={
        "date": "2026-05-01", "account_id": account["id"], "amount": -5000,
        "category_id": food["id"], "description": "Mercado",
    })
    client.post("/api/transactions", json={
        "date": "2026-05-02", "account_id": account["id"], "amount": -5000,
        "category_id": food["id"], "description": "Mercado dup",
    })
    res = client.get(f"/api/reconcile/suggestions?account_id={account['id']}")
    assert res.status_code == 200
    groups = res.get_json()
    assert len(groups) == 1
    assert groups[0]["amount"] == 5000
    assert len(groups[0]["transactions"]) == 2


def test_suggest_matches_requires_account(client):
    res = client.get("/api/reconcile/suggestions")
    assert res.status_code == 400
