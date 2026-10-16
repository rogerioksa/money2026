""" regressao: API web deve abrir empresa real e servir contas/lancamentos."""

from __future__ import annotations


def _client(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from gnc_lite import app_webview

    app = app_webview.create_app()
    app.testing = True
    return app.test_client()


def test_web_open_company_and_post(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)

    assert client.get("/").status_code == 200
    assert client.get("/api/companies").get_json() == {"companies": []}

    created = client.post(
        "/api/companies",
        json={"name": "Web Co", "admin_user": "admin", "admin_pass": "1234"},
    )
    assert created.status_code == 200

    accounts = client.get("/api/accounts").get_json()["accounts"]
    leaf = [a for a in accounts if not a["placeholder"]]
    assert len(leaf) >= 2
    cash = next(a for a in leaf if a["code"].startswith("1"))
    other = next(a for a in leaf if a["id"] != cash["id"] and a["code"][0] in "34")

    posted = client.post(
        "/api/transactions",
        json={
            "date": "2026-10-01",
            "description": "Venda web",
            "splits": [
                {"account_id": cash["id"], "minor_units": 10000},
                {"account_id": other["id"], "minor_units": -10000},
            ],
        },
    )
    assert posted.status_code == 200

    rows = client.get(
        f"/api/transactions/running-balance?account_id={cash['id']}"
    ).get_json()["rows"]
    assert len(rows) == 1
    assert rows[0]["balance"] == 10000
    assert rows[0]["debit"] == 10000


def test_web_select_and_validation(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    assert client.post("/api/companies/select", json={}).status_code == 404
    bad = client.post("/api/companies", json={"name": "", "admin_pass": "1234"})
    assert bad.status_code == 400


def _setup_company(client):
    created = client.post(
        "/api/companies",
        json={"name": "Web Co", "admin_user": "admin", "admin_pass": "1234"},
    )
    assert created.status_code == 200
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "1234"}
    )
    assert login.status_code == 200
    return client


def test_web_auth_me_logout(monkeypatch, tmp_path) -> None:
    client = _setup_company(_client(monkeypatch, tmp_path))
    me = client.get("/api/auth/me").get_json()
    assert me["user"]["username"] == "admin"
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").get_json() == {"user": None}


def test_web_accounts_crud(monkeypatch, tmp_path) -> None:
    client = _setup_company(_client(monkeypatch, tmp_path))
    leaf = [
        a
        for a in client.get("/api/accounts").get_json()["accounts"]
        if not a["placeholder"]
    ]
    parent = next(a for a in leaf if a["code"].startswith("1"))
    created = client.post(
        "/api/accounts",
        json={"code": "1.9.9", "name": "Caixa teste", "type": "ativo",
              "parent_id": parent["id"]},
    )
    assert created.status_code == 200, created.get_json()
    acc_id = created.get_json()["account"]["id"]
    dup = client.post(
        "/api/accounts",
        json={"code": "1.9.9", "name": "Duplicada", "type": "ativo"},
    )
    assert dup.status_code == 400
    updated = client.patch(
        f"/api/accounts/{acc_id}", json={"name": "Caixa teste 2"}
    )
    assert updated.status_code == 200
    assert updated.get_json()["account"]["name"] == "Caixa teste 2"


def test_web_reports(monkeypatch, tmp_path) -> None:
    client = _setup_company(_client(monkeypatch, tmp_path))
    for path in (
        "/api/reports/status",
        "/api/reports/trial-balance",
        "/api/reports/income",
        "/api/reports/balance-sheet",
        "/api/reports/cash-flow",
        "/api/reports/mei-annual?year=2026",
        "/api/reports/mei-monthly?year=2026&month=4",
    ):
        response = client.get(path)
        assert response.status_code == 200, (path, response.get_json())


def test_web_invoices_flow(monkeypatch, tmp_path) -> None:
    client = _setup_company(_client(monkeypatch, tmp_path))
    party = client.post(
        "/api/invoices/parties",
        json={"name": "Cliente A", "type": "cliente"},
    )
    assert party.status_code == 200
    party_id = party.get_json()["party"]["id"]
    issued = client.post(
        "/api/invoices/receivable",
        json={
            "party_id": party_id,
            "amount_minor": 5000,
            "issue_date": "2026-04-01",
            "due_date": "2026-04-10",
        },
    )
    assert issued.status_code == 200, issued.get_json()
    invoice_id = issued.get_json()["invoice"]["id"]
    listed = client.get("/api/invoices?open_only=1").get_json()["invoices"]
    assert any(i["id"] == invoice_id for i in listed)
    leaf = [
        a
        for a in client.get("/api/accounts").get_json()["accounts"]
        if not a["placeholder"] and a["code"].startswith("1")
    ]
    settled = client.post(
        f"/api/invoices/{invoice_id}/settle",
        json={"date": "2026-04-05", "cash_account_id": leaf[0]["id"]},
    )
    assert settled.status_code == 200, settled.get_json()
    assert settled.get_json()["invoice"]["status"] == "quitado"


def test_web_users_and_config(monkeypatch, tmp_path) -> None:
    client = _setup_company(_client(monkeypatch, tmp_path))
    created = client.post(
        "/api/users",
        json={"username": "op", "password": "1234", "role": "operador"},
    )
    assert created.status_code == 200, created.get_json()
    assert len(client.get("/api/users").get_json()["users"]) == 2
    config = client.get("/api/config").get_json()
    assert config["profile"] in ("pessoal", "mei")
    updated = client.put("/api/config", json={"profile": "mei"})
    assert updated.status_code == 200
    assert updated.get_json()["config"]["profile"] == "mei"


def test_web_reset_keeps_users_clears_ledger(monkeypatch, tmp_path) -> None:
    client = _setup_company(_client(monkeypatch, tmp_path))
    client.post(
        "/api/users",
        json={"username": "op", "password": "1234", "role": "operador"},
    )
    accounts = client.get("/api/accounts").get_json()["accounts"]
    leaf = [a for a in accounts if not a["placeholder"]]
    cash = next(a for a in leaf if a["code"].startswith("1"))
    other = next(a for a in leaf if a["id"] != cash["id"] and a["code"][0] in "34")
    client.post(
        "/api/transactions",
        json={
            "date": "2026-10-01",
            "description": "Venda",
            "splits": [
                {"account_id": cash["id"], "minor_units": 10000},
                {"account_id": other["id"], "minor_units": -10000},
            ],
        },
    )
    assert len(client.get("/api/transactions").get_json()["transactions"]) == 1

    reset = client.post("/api/companies/reset")
    assert reset.status_code == 200

    # Usuarios mantidos e sessao continua logada.
    assert len(client.get("/api/users").get_json()["users"]) == 2
    assert client.get("/api/auth/me").get_json()["user"]["username"] == "admin"
    # Lancamentos zerados e plano padrao recriado.
    assert client.get("/api/transactions").get_json() == {"transactions": []}
    codes = {a["code"] for a in client.get("/api/accounts").get_json()["accounts"]}
    assert {"1.1", "4.1"} <= codes


def test_web_card_account_limit_tracking(monkeypatch, tmp_path) -> None:
    client = _setup_company(_client(monkeypatch, tmp_path))
    created = client.post(
        "/api/accounts",
        json={"code": "2.4", "name": "Cartao Nubank", "kind": "cartao",
              "limit_minor": 500000, "parent_id": None},
    )
    assert created.status_code == 200, created.get_json()
    card = created.get_json()["account"]
    assert card["type"] == "passivo"
    assert card["limit_minor"] == 500000
    assert card["used_minor"] == 0
    assert card["available_minor"] == 500000

    bad = client.post(
        "/api/accounts",
        json={"code": "2.5", "name": "X", "kind": "pix", "type": "passivo"},
    )
    assert bad.status_code == 400

    cash = next(
        a for a in client.get("/api/accounts").get_json()["accounts"]
        if a["code"] == "1.1"
    )
    posted = client.post(
        "/api/transactions",
        json={
            "date": "2026-10-02",
            "description": "Fatura cartao",
            "splits": [
                {"account_id": card["id"], "minor_units": -120050},
                {"account_id": cash["id"], "minor_units": 120050},
            ],
        },
    )
    assert posted.status_code == 200
    card = next(
        a for a in client.get("/api/accounts").get_json()["accounts"]
        if a["code"] == "2.4"
    )
    assert card["used_minor"] == 120050
    assert card["available_minor"] == 500000 - 120050

    updated = client.patch(
        f"/api/accounts/{card['id']}", json={"limit_minor": 600000}
    )
    assert updated.status_code == 200
    assert updated.get_json()["account"]["available_minor"] == 600000 - 120050


def test_web_das_csv_download(monkeypatch, tmp_path) -> None:
    client = _setup_company(_client(monkeypatch, tmp_path))
    marked = client.post(
        "/api/obligations/mark", json={"key": "das:2020-03", "done": True}
    )
    assert marked.status_code == 200
    response = client.post("/api/exports/das-csv", json={"year": 2020})
    assert response.status_code == 200, response.get_json()
    filename = response.get_json()["filename"]
    assert filename == "DAS_2020_situacao.csv"
    target = tmp_path / "DB" / "exports" / filename
    assert target.exists()
    text = target.read_text(encoding="utf-8").lstrip("\ufeff")
    rows = [line for line in text.strip().splitlines() if line]
    assert rows[0] == "Competência;Vencimento;Situação;Detalhe"
    assert len(rows) == 13
    march = next(line for line in rows if line.startswith("03/2020;"))
    assert ";Paga;" in march
    january = next(line for line in rows if line.startswith("01/2020;"))
    assert ";Atrasada;" in january
    opened = client.get(f"/api/exports/open?file={filename}")
    assert opened.status_code in (200, 500)
    assert client.get("/api/exports/open?file=..").status_code == 400
    assert client.get("/api/exports/open?file=../x.csv").status_code == 404
    assert client.get("/api/exports/open?file=nope.csv").status_code == 404


def test_web_cnpj_fill_and_ficha(monkeypatch, tmp_path) -> None:
    from gnc_lite.services import cnpj as cnpj_service

    client = _setup_company(_client(monkeypatch, tmp_path))
    payload = {
        "cnpj": "11222333000181",
        "descricao_situacao_cadastral": "ATIVA",
        "razao_social": "FULANO MEI",
        "cnae_fiscal_descricao": "Comércio varejista",
        "municipio": "SAO PAULO",
        "uf": "SP",
        "data_inicio_atividade": "2020-02-01",
        "opcao_pelo_mei": True,
    }
    monkeypatch.setattr(
        cnpj_service, "lookup", lambda digits, timeout=12: dict(payload)
    )
    filled = client.post("/api/cnpj/fill", json={"cnpj": "11.222.333/0001-81"})
    assert filled.status_code == 200, filled.get_json()
    fields = filled.get_json()["fields"]
    assert fields["nome_empresarial"] == "FULANO MEI"
    assert fields["cnpj"] == "11.222.333/0001-81"
    assert fields["municipio"] == "Sao Paulo"
    assert filled.get_json()["warnings"] == []

    ficha = client.post(
        "/api/exports/cnpj-ficha", json={"cnpj": "11.222.333/0001-81"}
    )
    assert ficha.status_code == 200, ficha.get_json()
    assert ficha.get_json()["filename"] == "CNPJ_11222333000181_ficha.json"

    bad = client.post("/api/cnpj/fill", json={"cnpj": "123"})
    assert bad.status_code == 400
