"""Relatórios: gastos por categoria, patrimônio líquido, fluxo de caixa."""

from __future__ import annotations

from money99.db.repository import Repository
from money99.db.session import connect, init_db, make_session
from money99.domain.account import Account
from money99.domain.transaction import Transaction
from money99.services.reports import (
    cash_flow,
    dashboard,
    net_worth,
    spending_by_category,
)


def setup_db(tmp_path):
    engine = connect(tmp_path / "r.sqlite")
    init_db(engine)
    return make_session(engine)


def seed(session):
    repo = Repository(session)
    account = repo.add_account(Account(name="Banco", type="bank", initial_balance=100000))
    cats = {c.name: c for c in repo.list_categories()}
    repo.add_transaction(Transaction(
        date="2026-03-10", account_id=account.id, amount=-4000,
        category_id=cats["Alimentação"].id,
    ))
    repo.add_transaction(Transaction(
        date="2026-03-20", account_id=account.id, amount=-2000,
        category_id=cats["Alimentação"].id,
    ))
    repo.add_transaction(Transaction(
        date="2026-04-05", account_id=account.id, amount=50000,
        category_id=cats["Salário"].id,
    ))
    session.commit()
    return repo, account, cats


def test_spending_by_category(tmp_path):
    repo, _, cats = seed(setup_db(tmp_path))
    result = spending_by_category(repo, "2026-01-01", "2026-12-31")
    food = next(r for r in result if r["category"] == "Alimentação")
    assert food["total"] == 6000
    assert result[0]["category"] == "Alimentação"  # ordenado desc


def test_spending_income_kind(tmp_path):
    repo, _, _ = seed(setup_db(tmp_path))
    result = spending_by_category(repo, "2026-01-01", "2026-12-31", kind="income")
    assert result == [{"category_id": result[0]["category_id"], "category": "Salário",
                       "total": 50000}]


def test_net_worth(tmp_path):
    repo, account, _ = seed(setup_db(tmp_path))
    worth = net_worth(repo)
    # 100000 - 4000 - 2000 + 50000
    assert worth["total"] == 144000
    assert worth["accounts"][0]["balance"] == 144000


def test_net_worth_as_of(tmp_path):
    repo, _, _ = seed(setup_db(tmp_path))
    worth = net_worth(repo, as_of="2026-03-31")
    assert worth["total"] == 100000 - 6000  # exclui salário de abril


def test_net_worth_ignores_future_transactions(tmp_path):
    repo, account, cats = seed(setup_db(tmp_path))
    repo.add_transaction(Transaction(
        date="2200-01-01", account_id=account.id, amount=-9000,
        category_id=cats["Alimentação"].id,
    ))
    assert net_worth(repo)["total"] == 144000
    assert net_worth(repo, as_of="2200-12-31")["total"] == 144000 - 9000


def test_dashboard_separates_future_entries(tmp_path):
    repo, account, cats = seed(setup_db(tmp_path))
    repo.add_transaction(Transaction(
        date="2200-01-01", account_id=account.id, amount=-700,
        category_id=cats["Alimentação"].id,
    ))
    data = dashboard(repo)
    entry = next(a for a in data["accounts"] if a["account_id"] == account.id)
    assert entry["balance"] == 144000
    assert entry["future"] == -700
    assert data["assets_total"] == 144000


def test_cash_flow(tmp_path):
    repo, _, _ = seed(setup_db(tmp_path))
    flow = cash_flow(repo, "2026-01-01", "2026-12-31")
    assert [f["month"] for f in flow] == ["2026-03", "2026-04"]
    march = flow[0]
    assert march["inflow"] == 0 and march["outflow"] == 6000 and march["net"] == -6000
    april = flow[1]
    assert april["inflow"] == 50000 and april["outflow"] == 0 and april["net"] == 50000


def test_reports_api(client):
    account = client.post("/api/accounts", json={
        "name": "Banco", "type": "bank", "initial_balance": 100000,
    }).get_json()
    food = next(c for c in client.get("/api/categories?kind=expense").get_json()
                if c["name"] == "Alimentação")
    client.post("/api/transactions", json={
        "date": "2026-06-01", "account_id": account["id"], "amount": -3000,
        "category_id": food["id"],
    })

    res = client.get("/api/reports/spending?start=2026-01-01&end=2026-12-31")
    assert res.status_code == 200
    assert res.get_json()[0]["total"] == 3000

    res = client.get("/api/reports/net-worth")
    assert res.get_json()["total"] == 97000

    res = client.get("/api/reports/cash-flow?start=2026-01-01&end=2026-12-31")
    assert res.get_json()[0]["outflow"] == 3000


def test_reports_api_validation(client):
    assert client.get("/api/reports/spending").status_code == 400
    assert client.get("/api/reports/cash-flow").status_code == 400
    assert client.get("/api/reports/spending?start=2026-01-01&end=2026-12-31&kind=x"
                      ).status_code == 400


def test_dashboard_credit_and_totals(tmp_path):
    repo = Repository(setup_db(tmp_path))
    repo.add_account(Account(name="Banco", type="bank", initial_balance=100000))
    repo.add_account(Account(name="Cartão", type="credit",
                             credit_limit=500000, initial_balance=-120000))

    data = dashboard(repo)
    assert data["assets_total"] == 100000
    assert data["net_worth"] == 100000 - 120000
    assert data["credit"]["limit_total"] == 500000
    assert data["credit"]["used_total"] == 120000
    assert data["credit"]["available_total"] == 380000
    assert len(data["credit"]["accounts"]) == 1
    by_name = {a["name"]: a for a in data["accounts"]}
    assert by_name["Banco"]["available"] == 100000
    assert by_name["Cartão"]["available"] == 380000


def test_dashboard_available_includes_limit_for_bank(tmp_path):
    repo = Repository(setup_db(tmp_path))
    repo.add_account(Account(name="ITAU", type="bank", initial_balance=20105,
                             credit_limit=427000))
    data = dashboard(repo)
    entry = data["accounts"][0]
    assert entry["balance"] == 20105
    assert entry["credit_limit"] == 427000
    assert entry["available"] == 447105
    # Conta bancária com limite também aparece no resumo de crédito,
    # mas o saldo continua compondo o patrimônio.
    assert data["assets_total"] == 20105
    assert data["credit"]["limit_total"] == 427000
    assert data["credit"]["used_total"] == 0
    assert data["credit"]["available_total"] == 447105


def test_dashboard_api(client):
    client.post("/api/accounts", json={"name": "Banco", "type": "bank",
                                       "initial_balance": 100000})
    client.post("/api/accounts", json={"name": "Cartão", "type": "credit",
                                       "credit_limit": 500000, "initial_balance": -120000})
    res = client.get("/api/reports/dashboard")
    assert res.status_code == 200
    body = res.get_json()
    assert body["credit"]["used_total"] == 120000
    assert body["assets_total"] == 100000


def test_print_report_endpoint(client):
    client.post("/api/accounts", json={"name": "Banco", "type": "bank",
                                       "initial_balance": 100000})
    res = client.get("/reports/print?year=2026")
    assert res.status_code == 200
    assert "Relatório" in res.get_data(as_text=True)
