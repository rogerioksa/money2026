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


def test_descriptions_index_orders_by_usage(client):
    account = create_account(client)
    add_txn(client, account["id"], "MERCADO")
    add_txn(client, account["id"], "MERCADO")
    add_txn(client, account["id"], "FARMACIA")
    add_txn(client, account["id"], "", amount=-500)

    body = client.get("/api/transactions/descriptions").get_json()
    assert body[0] == {"description": "MERCADO", "count": 2}
    assert {row["description"] for row in body} == {"MERCADO", "FARMACIA"}


def test_descriptions_index_filters_substring_case_insensitive(client):
    account = create_account(client)
    add_txn(client, account["id"], "MERCADO CENTRAL")
    add_txn(client, account["id"], "FARMACIA")

    body = client.get("/api/transactions/descriptions?q=central").get_json()
    assert [row["description"] for row in body] == ["MERCADO CENTRAL"]


def test_descriptions_index_prefers_prefix_matches(client):
    account = create_account(client)
    for _ in range(3):
        add_txn(client, account["id"], "SUPERMERCADO")
    add_txn(client, account["id"], "MERCADO")

    body = client.get("/api/transactions/descriptions?q=MERCADO").get_json()
    assert [row["description"] for row in body] == ["MERCADO", "SUPERMERCADO"]


def test_descriptions_index_respects_limit(client):
    account = create_account(client)
    for name in ("ALFA", "BETA", "GAMA"):
        add_txn(client, account["id"], name)

    body = client.get("/api/transactions/descriptions?limit=2").get_json()
    assert len(body) == 2


def test_descriptions_index_limit_zero_returns_all(client):
    account = create_account(client)
    for index in range(25):
        add_txn(client, account["id"], f"DESPESA {index:02d}")

    body = client.get("/api/transactions/descriptions?limit=0").get_json()
    assert len(body) == 25


def test_title_descriptions_index(client):
    def add_title(description):
        res = client.post("/api/titles", json={
            "type": "payable",
            "description": description,
            "amount": 10000,
            "due_date": "2026-06-10",
        })
        assert res.status_code == 201

    add_title("ENERGIA")
    add_title("ENERGIA")
    add_title("AGUA")

    body = client.get("/api/titles/descriptions").get_json()
    assert body[0] == {"description": "ENERGIA", "count": 2}
    assert {row["description"] for row in body} == {"ENERGIA", "AGUA"}

    filtered = client.get("/api/titles/descriptions?q=gua").get_json()
    assert [row["description"] for row in filtered] == ["AGUA"]


def test_title_suggest_link_falls_back_to_transactions(client):
    account = create_account(client)
    cat = categories(client)[0]
    add_txn(client, account["id"], "ALUGUEL", cat["id"])

    body = client.get("/api/titles/suggest-link?description=ALUGUEL").get_json()
    assert body["category_id"] == cat["id"]
    assert body["favorecido_id"] is None
