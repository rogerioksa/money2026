"""Relatórios do MEI: faturamento, despesas, lucro e limite anual."""

from __future__ import annotations

import pytest

from money99.db.repository import Repository
from money99.db.session import connect, init_db, make_session
from money99.domain.profile import MeiActivity, Profile
from money99.domain.transaction import Transaction
from money99.services.mei import monthly_caderno, monthly_report, period_report


def _repo_with_business(tmp_path):
    engine = connect(tmp_path / "mei.sqlite")
    init_db(engine)
    session = make_session(engine)
    base = Repository(session)
    profile = base.add_profile(Profile(name="MEI", kind="business", annual_limit=8_100_000))
    repo = Repository(session, profile.id)
    repo.seed_default_categories(profile.id)
    repo.add_account(_bank(repo, "MEI"))
    return repo, profile


def _bank(repo, name):
    from money99.domain.account import Account

    return repo.add_account(Account(name=name, type="bank", initial_balance=0))


def _cats(repo):
    cats = repo.list_categories()
    return (
        next(c for c in cats if c.kind == "income"),
        next(c for c in cats if c.kind == "expense"),
    )


def test_monthly_report_totals(tmp_path):
    repo, _ = _repo_with_business(tmp_path)
    acc = repo.list_accounts()[0]
    inc, exp = _cats(repo)
    repo.add_transaction(Transaction(date="2026-03-10", account_id=acc.id,
                                     amount=500_000, category_id=inc.id))
    repo.add_transaction(Transaction(date="2026-03-15", account_id=acc.id,
                                     amount=-80_000, category_id=exp.id))
    repo.add_transaction(Transaction(date="2026-04-01", account_id=acc.id,
                                     amount=300_000, category_id=inc.id))

    report = monthly_report(repo, 2026)
    assert report["revenue_total"] == 800_000
    assert report["expense_total"] == 80_000
    assert report["result_total"] == 720_000
    march = next(m for m in report["months"] if m["month"] == 3)
    assert march["revenue"] == 500_000
    assert march["result"] == 420_000


def test_monthly_report_limit(tmp_path):
    repo, _ = _repo_with_business(tmp_path)
    acc = repo.list_accounts()[0]
    inc, _ = _cats(repo)
    repo.add_transaction(Transaction(date="2026-01-05", account_id=acc.id,
                                     amount=9_000_000, category_id=inc.id))
    report = monthly_report(repo, 2026)
    assert report["annual_limit"] == 8_100_000
    assert report["limit_exceeded"] is True
    assert report["limit_remaining"] < 0


def test_uncategorized_and_transfers_ignored(tmp_path):
    repo, _ = _repo_with_business(tmp_path)
    acc = repo.list_accounts()[0]
    other = _bank(repo, "Outra")
    # sem categoria -> ignorado nos totais
    repo.add_transaction(Transaction(date="2026-05-01", account_id=acc.id, amount=100_000))
    # transferência -> ignorada
    repo.add_transaction(Transaction(date="2026-05-02", account_id=acc.id, amount=-50_000,
                                     transfer_account_id=other.id))
    report = monthly_report(repo, 2026)
    assert report["revenue_total"] == 0
    assert report["expense_total"] == 0


def test_period_report(tmp_path):
    repo, _ = _repo_with_business(tmp_path)
    acc = repo.list_accounts()[0]
    inc, exp = _cats(repo)
    repo.add_transaction(Transaction(date="2026-03-10", account_id=acc.id,
                                     amount=200_000, category_id=inc.id))
    repo.add_transaction(Transaction(date="2026-05-10", account_id=acc.id,
                                     amount=-30_000, category_id=exp.id))
    q1 = period_report(repo, "2026-01-01", "2026-03-31")
    assert q1["revenue"] == 200_000
    assert q1["expense"] == 0
    year = period_report(repo, "2026-01-01", "2026-12-31")
    assert year["revenue"] == 200_000
    assert year["result"] == 170_000


def test_mei_api_report(client):
    business = client.post("/api/profiles", json={
        "name": "MEI", "kind": "business", "annual_limit": 8_100_000,
    }).get_json()
    client.put("/api/auth/profile", json={"profile_id": business["id"]})
    client.post("/api/accounts", json={"name": "MEI", "type": "bank"})
    acc = client.get("/api/accounts").get_json()[0]
    cats = client.get("/api/categories").get_json()
    inc = next(c for c in cats if c["kind"] == "income")
    client.post("/api/transactions", json={
        "date": "2026-03-10", "account_id": acc["id"], "amount": 400_000,
        "category_id": inc["id"],
    })
    res = client.get("/api/mei/report?year=2026")
    assert res.status_code == 200
    assert res.get_json()["revenue_total"] == 400_000


def test_mei_api_requires_year(client):
    assert client.get("/api/mei/report").status_code == 400


def test_mei_print_endpoint(client):
    business = client.post("/api/profiles", json={
        "name": "MEI", "kind": "business", "legal_name": "Fulano ME",
        "cnpj": "00.000.000/0001-00",
    }).get_json()
    client.put("/api/auth/profile", json={"profile_id": business["id"]})
    res = client.get("/reports/mei?year=2026")
    assert res.status_code == 200
    assert "Fulano ME" in res.get_data(as_text=True)


def test_monthly_caderno_lines_and_profit(tmp_path):
    repo, _ = _repo_with_business(tmp_path)
    acc = repo.list_accounts()[0]
    inc, exp = _cats(repo)
    repo.add_transaction(Transaction(date="2026-05-03", account_id=acc.id, amount=100_000,
                                     category_id=inc.id, description="Venda PF"))
    repo.add_transaction(Transaction(date="2026-05-10", account_id=acc.id, amount=250_000,
                                     category_id=inc.id, description="Venda PJ",
                                     doc_issued=True))
    repo.add_transaction(Transaction(date="2026-05-12", account_id=acc.id, amount=-40_000,
                                     category_id=exp.id, description="Luz"))

    data = monthly_caderno(repo, 2026, 5)
    assert data["activity"] == "servicos"
    assert [line["number"] for line in data["lines"]] == [7, 8, 9]
    assert [line["amount"] for line in data["lines"]] == [100_000, 250_000, 350_000]
    assert data["sales_without_doc"] == 100_000
    assert data["sales_with_doc"] == 250_000
    assert data["sales_total"] == 350_000
    assert data["expenses_total"] == 40_000
    assert data["profit"] == 310_000
    assert len(data["sales"]) == 2
    assert {sale["description"] for sale in data["sales"]} == {"Venda PF", "Venda PJ"}
    assert data["daily"][2]["sales"] == 100_000  # dia 3
    assert data["daily"][11]["expenses"] == 40_000  # dia 12
    assert data["period_label"] == "01/05/2026 a 31/05/2026"


def test_monthly_caderno_activity_lines(tmp_path):
    repo, profile = _repo_with_business(tmp_path)
    profile.activity = MeiActivity.COMERCIO
    repo.update_profile(profile)
    data = monthly_caderno(repo, 2026, 5)
    assert [line["number"] for line in data["lines"]] == [1, 2, 3]
    assert data["activity_label"] == "COMÉRCIO"


def test_monthly_caderno_rejects_invalid_month(tmp_path):
    repo, _ = _repo_with_business(tmp_path)
    with pytest.raises(ValueError):
        monthly_caderno(repo, 2026, 13)


def test_mei_caderno_api(client):
    business = client.post("/api/profiles", json={
        "name": "MEI", "kind": "business", "activity": "comercio",
    }).get_json()
    client.put("/api/auth/profile", json={"profile_id": business["id"]})
    client.post("/api/accounts", json={"name": "MEI", "type": "bank"})
    acc = client.get("/api/accounts").get_json()[0]
    inc = next(c for c in client.get("/api/categories").get_json() if c["kind"] == "income")
    client.post("/api/transactions", json={
        "date": "2026-05-03", "account_id": acc["id"], "amount": 120_000,
        "category_id": inc["id"], "doc_issued": True,
    })
    res = client.get("/api/mei/caderno?year=2026&month=5")
    assert res.status_code == 200
    body = res.get_json()
    assert body["activity"] == "comercio"
    assert body["sales_with_doc"] == 120_000
    assert [line["number"] for line in body["lines"]] == [1, 2, 3]


def test_mei_caderno_api_validation(client):
    assert client.get("/api/mei/caderno?year=2026").status_code == 400
    assert client.get("/api/mei/caderno?year=2026&month=13").status_code == 400


def test_transaction_doc_issued_roundtrip(client):
    client.post("/api/accounts", json={"name": "Caixa", "type": "cash"})
    acc = client.get("/api/accounts").get_json()[0]
    inc = next(c for c in client.get("/api/categories").get_json() if c["kind"] == "income")
    created = client.post("/api/transactions", json={
        "date": "2026-06-01", "account_id": acc["id"], "amount": 10_000,
        "category_id": inc["id"], "doc_issued": True,
    }).get_json()
    assert created["doc_issued"] is True
    txn = client.get("/api/transactions").get_json()[0]
    assert txn["doc_issued"] is True


def test_mei_print_monthly_caderno(client):
    business = client.post("/api/profiles", json={
        "name": "MEI", "kind": "business", "legal_name": "Fulano ME",
        "cnpj": "00.000.000/0001-00", "activity": "servicos",
    }).get_json()
    client.put("/api/auth/profile", json={"profile_id": business["id"]})
    res = client.get("/reports/mei?year=2026&month=5")
    html = res.get_data(as_text=True)
    assert res.status_code == 200
    assert "RELATÓRIO MENSAL DAS RECEITAS BRUTAS" in html
    assert "Fulano ME" in html
    assert "01/05/2026 a 31/05/2026" in html
