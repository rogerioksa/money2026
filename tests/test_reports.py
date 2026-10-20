"""Relatórios: gastos por categoria, patrimônio líquido, fluxo de caixa."""

from __future__ import annotations

from money99.db.repository import Repository
from money99.db.session import connect, init_db, make_session
from money99.domain.account import Account
from money99.domain.transaction import Transaction
from money99.services.reports import cash_flow, net_worth, spending_by_category


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
