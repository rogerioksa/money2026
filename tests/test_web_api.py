"""Regressão ponta-a-ponta da API REST (contas, categorias, transações)."""

from __future__ import annotations


def create_account(client, name="Banco", type_="bank", initial=100000):
    res = client.post("/api/accounts", json={"name": name, "type": type_,
                                             "initial_balance": initial})
    assert res.status_code == 201
    return res.get_json()


def expense_category(client):
    res = client.get("/api/categories?kind=expense")
    return res.get_json()[0]


def income_category(client):
    res = client.get("/api/categories?kind=income")
    return res.get_json()[0]


def test_accounts_crud(client):
    account = create_account(client)
    assert account["balance"] == 100000

    res = client.get("/api/accounts")
    assert len(res.get_json()) == 1

    res = client.put(f"/api/accounts/{account['id']}",
                     json={"name": "Banco Inter", "type": "bank",
                           "initial_balance": 50000, "active": True})
    assert res.status_code == 200
    assert res.get_json()["name"] == "Banco Inter"
    assert res.get_json()["balance"] == 50000

    res = client.delete(f"/api/accounts/{account['id']}")
    assert res.status_code == 200
    assert client.get("/api/accounts").get_json() == []


def test_account_validation_errors(client):
    res = client.post("/api/accounts", json={"name": "  "})
    assert res.status_code == 400
    res = client.post("/api/accounts", json={"name": "X", "type": "crypto"})
    assert res.status_code == 400
    res = client.get("/api/accounts/999")
    assert res.status_code == 404


def test_categories_seeded_and_filterable(client):
    all_cats = client.get("/api/categories").get_json()
    assert len(all_cats) == 12
    expense = client.get("/api/categories?kind=expense").get_json()
    assert all(c["kind"] == "expense" for c in expense)
    res = client.post("/api/categories", json={"name": "Pets", "kind": "expense"})
    assert res.status_code == 201
    res = client.post("/api/categories", json={"name": "X", "kind": "invalido"})
    assert res.status_code == 400


def test_transaction_crud_and_balance(client):
    account = create_account(client)
    cat = expense_category(client)

    res = client.post("/api/transactions", json={
        "date": "2026-10-05", "description": "Mercado", "account_id": account["id"],
        "amount": -4532, "category_id": cat["id"],
    })
    assert res.status_code == 201
    txn = res.get_json()
    assert txn["amount"] == -4532

    res = client.get(f"/api/accounts/{account['id']}/balance")
    assert res.get_json()["balance"] == 100000 - 4532

    res = client.put(f"/api/transactions/{txn['id']}", json={
        "date": "2026-10-06", "description": "Mercado pão", "account_id": account["id"],
        "amount": -5000, "category_id": cat["id"],
    })
    assert res.status_code == 200
    assert res.get_json()["amount"] == -5000

    res = client.delete(f"/api/transactions/{txn['id']}")
    assert res.status_code == 200
    assert client.get("/api/transactions").get_json() == []


def test_transaction_validation_via_api(client):
    account = create_account(client)
    cat = expense_category(client)

    res = client.post("/api/transactions", json={
        "date": "2026-10-05", "account_id": account["id"], "amount": -100,
    })
    assert res.status_code == 400  # sem categoria

    res = client.post("/api/transactions", json={
        "date": "19/10/2026", "account_id": account["id"], "amount": -100,
        "category_id": cat["id"],
    })
    assert res.status_code == 400  # data não-ISO

    res = client.post("/api/transactions", json={
        "date": "2026-10-05", "account_id": account["id"], "amount": 0,
        "category_id": cat["id"],
    })
    assert res.status_code == 400  # zero

    res = client.post("/api/transactions", json={
        "date": "2026-10-05", "account_id": 999, "amount": -100,
        "category_id": cat["id"],
    })
    assert res.status_code == 400


def test_transfer_via_api(client):
    checking = create_account(client, "Conta")
    savings = create_account(client, "Poupança", initial=0)

    res = client.post("/api/transactions", json={
        "date": "2026-10-10", "account_id": checking["id"], "amount": -30000,
        "transfer_account_id": savings["id"],
    })
    assert res.status_code == 201

    assert client.get(f"/api/accounts/{checking['id']}/balance").get_json()["balance"] == 70000
    assert client.get(f"/api/accounts/{savings['id']}/balance").get_json()["balance"] == 30000

    # transferência aparece no extrato das duas contas
    res = client.get(f"/api/transactions?account_id={savings['id']}")
    assert len(res.get_json()) == 1


def test_splits_via_api(client):
    account = create_account(client)
    cats = {c["name"]: c for c in client.get("/api/categories?kind=expense").get_json()}

    res = client.post("/api/transactions", json={
        "date": "2026-10-07", "account_id": account["id"], "amount": -9000,
        "description": "Viagem",
        "splits": [
            {"category_id": cats["Transporte"]["id"], "amount": -6000},
            {"category_id": cats["Lazer"]["id"], "amount": -3000},
        ],
    })
    assert res.status_code == 201

    res = client.get(f"/api/transactions?category_id={cats['Lazer']['id']}")
    assert len(res.get_json()) == 1
    res = client.get(f"/api/transactions?category_id={cats['Saúde']['id']}")
    assert res.get_json() == []


def test_transaction_filters(client):
    account = create_account(client)
    other = create_account(client, "Outra", initial=0)
    cat = expense_category(client)
    for date in ("2026-09-30", "2026-10-15", "2026-11-02"):
        client.post("/api/transactions", json={
            "date": date, "account_id": account["id"], "amount": -100,
            "category_id": cat["id"],
        })

    res = client.get("/api/transactions?start=2026-10-01&end=2026-10-31")
    assert len(res.get_json()) == 1

    res = client.get(f"/api/transactions?account_id={other['id']}")
    assert res.get_json() == []


def test_reconcile_endpoint(client):
    account = create_account(client)
    cat = expense_category(client)
    txn = client.post("/api/transactions", json={
        "date": "2026-10-05", "account_id": account["id"], "amount": -1000,
        "category_id": cat["id"],
    }).get_json()

    res = client.post(f"/api/transactions/{txn['id']}/reconcile", json={"reconciled": True})
    assert res.status_code == 200

    res = client.get("/api/transactions?reconciled=1")
    assert len(res.get_json()) == 1
    res = client.get("/api/transactions?reconciled=0")
    assert res.get_json() == []


def test_cannot_delete_account_with_transactions(client):
    account = create_account(client)
    cat = expense_category(client)
    client.post("/api/transactions", json={
        "date": "2026-10-05", "account_id": account["id"], "amount": -100,
        "category_id": cat["id"],
    })
    res = client.delete(f"/api/accounts/{account['id']}")
    assert res.status_code == 400


def test_persist_across_app_instances(tmp_path):
    """Dados persistem no SQLite entre 'reinícios' do app."""
    from money99.app import create_app

    db_file = tmp_path / "persist.sqlite"
    app1 = create_app(str(db_file))
    app1.config["TESTING"] = True
    res = app1.test_client().post("/api/accounts", json={"name": "Banco", "type": "bank"})
    assert res.status_code == 201

    app2 = create_app(str(db_file))
    app2.config["TESTING"] = True
    accounts = app2.test_client().get("/api/accounts").get_json()
    assert len(accounts) == 1
    assert accounts[0]["name"] == "Banco"
