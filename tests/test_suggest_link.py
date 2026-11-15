"""Auto-vínculo por descrição: categoria e centro de custo independentes."""

from __future__ import annotations


def create_account(client, name="Banco", initial=100000):
    res = client.post("/api/accounts", json={
        "name": name, "type": "bank", "initial_balance": initial,
    })
    assert res.status_code == 201
    return res.get_json()


def create_cost_center(client, name):
    res = client.post("/api/cost-centers", json={"name": name})
    assert res.status_code == 201
    return res.get_json()


def categories(client, kind="expense"):
    return client.get(f"/api/categories?kind={kind}").get_json()


def add_txn(client, account_id, description, category_id=None, cost_center_id=None, amount=-1000):
    res = client.post("/api/transactions", json={
        "date": "2026-05-10",
        "description": description,
        "account_id": account_id,
        "amount": amount,
        "category_id": category_id,
        "cost_center_id": cost_center_id,
    })
    assert res.status_code == 201
    return res.get_json()


def test_suggest_category_ignores_cost_center_variation(client):
    account = create_account(client)
    cat = categories(client)[0]
    cc1 = create_cost_center(client, "Obra A")
    cc2 = create_cost_center(client, "Obra B")

    add_txn(client, account["id"], "MERCADO", cat["id"], cc1["id"])
    add_txn(client, account["id"], "MERCADO", cat["id"], cc2["id"])
    add_txn(client, account["id"], "MERCADO", cat["id"], None)

    res = client.get("/api/transactions/suggest-link?description=mercado")
    assert res.status_code == 200
    body = res.get_json()
    assert body["category_id"] == cat["id"]
    # O centro de custo é um complemento: a categoria principal não depende dele.
    assert body["cost_center_id"] in (cc1["id"], cc2["id"], None)


def test_suggest_cost_center_without_category(client):
    account = create_account(client)
    cc = create_cost_center(client, "Projeto X")
    add_txn(client, account["id"], "UBER", None, cc["id"])

    body = client.get(
        "/api/transactions/suggest-link?description=UBER"
    ).get_json()
    assert body == {"category_id": None, "cost_center_id": cc["id"]}


def test_suggest_link_uses_splits(client):
    account = create_account(client)
    cat = categories(client)[0]
    res = client.post("/api/transactions", json={
        "date": "2026-05-11",
        "description": "FEIRA E UBER",
        "account_id": account["id"],
        "amount": -3000,
        "splits": [{"category_id": cat["id"], "amount": -3000}],
    })
    assert res.status_code == 201

    body = client.get(
        "/api/transactions/suggest-link?description=feira e uber"
    ).get_json()
    assert body["category_id"] == cat["id"]


def test_title_suggest_link_and_cost_center_roundtrip(client):
    account = create_account(client)
    cat = categories(client)[0]
    cc = create_cost_center(client, "Projeto Y")

    res = client.post("/api/titles", json={
        "type": "payable",
        "description": "ENERGIA",
        "amount": 25000,
        "due_date": "2026-06-10",
        "category_id": cat["id"],
        "cost_center_id": cc["id"],
    })
    assert res.status_code == 201
    title = res.get_json()
    assert title["category_id"] == cat["id"]
    assert title["cost_center_id"] == cc["id"]

    body = client.get("/api/titles/suggest-link?description=energia").get_json()
    assert body["category_id"] == cat["id"]
    assert body["cost_center_id"] == cc["id"]

    pay = client.post(f"/api/titles/{title['id']}/pay", json={
        "paid_date": "2026-06-10",
        "amount": 25000,
        "account_id": account["id"],
    })
    assert pay.status_code == 200

    txns = client.get(f"/api/transactions?account_id={account['id']}").get_json()
    assert txns[0]["category_id"] == cat["id"]
    assert txns[0]["cost_center_id"] == cc["id"]


def test_title_suggest_link_falls_back_to_transactions(client):
    account = create_account(client)
    cat = categories(client)[0]
    add_txn(client, account["id"], "ALUGUEL", cat["id"])

    body = client.get("/api/titles/suggest-link?description=ALUGUEL").get_json()
    assert body["category_id"] == cat["id"]
    assert body["favorecido_id"] is None
