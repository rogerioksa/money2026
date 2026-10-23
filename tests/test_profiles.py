"""Perfis: CRUD, troca de perfil ativo e isolamento de dados por perfil."""

from __future__ import annotations

from money99.db.repository import Repository
from money99.db.session import connect, init_db, make_session
from money99.domain.account import Account
from money99.domain.profile import DEFAULT_ANNUAL_LIMIT, Profile


def _personal_id(client) -> int:
    profiles = client.get("/api/profiles").get_json()
    return next(p["id"] for p in profiles if p["kind"] == "personal")


def test_default_personal_profile_created(app):
    with app.test_client() as c:
        c.post("/api/auth/setup", json={"username": "u", "password": "1234"})
        profiles = c.get("/api/profiles").get_json()
        assert len(profiles) == 1
        assert profiles[0]["kind"] == "personal"
        assert profiles[0]["name"] == "Pessoal"
        assert profiles[0]["annual_limit"] == 0


def test_personal_profile_has_no_annual_limit(client):
    created = client.post("/api/profiles", json={"name": "Pessoal 2", "kind": "personal"}).get_json()
    assert created["annual_limit"] == 0


def test_create_business_profile_seeds_categories(client):
    res = client.post("/api/profiles", json={
        "name": "Meu MEI", "kind": "business", "cnpj": "12.345.678/0001-99",
    })
    assert res.status_code == 201
    pid = res.get_json()["id"]
    assert res.get_json()["annual_limit"] == DEFAULT_ANNUAL_LIMIT
    # Troca para o perfil e confere que há categorias semeadas
    client.put("/api/auth/profile", json={"profile_id": pid})
    cats = client.get("/api/categories").get_json()
    assert len(cats) >= 12
    assert {c["kind"] for c in cats} == {"income", "expense"}


def test_switch_profile_persists_in_session(client):
    personal = _personal_id(client)
    created = client.post("/api/profiles", json={"name": "MEI", "kind": "business"}).get_json()
    res = client.put("/api/auth/profile", json={"profile_id": created["id"]})
    assert res.status_code == 200
    assert client.get("/api/auth/status").get_json()["profile_id"] == created["id"]
    client.put("/api/auth/profile", json={"profile_id": personal})
    assert client.get("/api/auth/status").get_json()["profile_id"] == personal


def test_switch_to_unknown_profile(client):
    assert client.put("/api/auth/profile", json={"profile_id": 9999}).status_code == 404


def test_data_isolation_between_profiles(client):
    personal = _personal_id(client)
    business = client.post("/api/profiles", json={"name": "MEI", "kind": "business"}).get_json()

    client.post("/api/accounts", json={"name": "Pessoal", "type": "bank"})

    client.put("/api/auth/profile", json={"profile_id": business["id"]})
    client.post("/api/accounts", json={"name": "MEI", "type": "bank"})

    assert [a["name"] for a in client.get("/api/accounts").get_json()] == ["MEI"]

    client.put("/api/auth/profile", json={"profile_id": personal})
    assert [a["name"] for a in client.get("/api/accounts").get_json()] == ["Pessoal"]


def test_cannot_delete_profile_with_data(client):
    personal = _personal_id(client)
    client.post("/api/accounts", json={"name": "Conta", "type": "bank"})
    res = client.delete(f"/api/profiles/{personal}")
    assert res.status_code == 400


def test_cannot_delete_last_profile(client):
    personal = _personal_id(client)
    res = client.delete(f"/api/profiles/{personal}")
    # tem dados? não — mas é o único perfil
    assert res.status_code == 400


def test_delete_empty_second_profile(client):
    created = client.post("/api/profiles", json={"name": "Extra", "kind": "personal"}).get_json()
    res = client.delete(f"/api/profiles/{created['id']}")
    assert res.status_code == 200
    names = [p["name"] for p in client.get("/api/profiles").get_json()]
    assert "Extra" not in names


def test_update_business_profile(client):
    created = client.post("/api/profiles", json={"name": "MEI", "kind": "business"}).get_json()
    res = client.put(f"/api/profiles/{created['id']}", json={
        "name": "MEI Renomeado", "kind": "business", "cnpj": "00.000.000/0001-00",
        "legal_name": "Fulano ME", "annual_limit": 8100000,
    })
    assert res.status_code == 200
    body = res.get_json()
    assert body["name"] == "MEI Renomeado"
    assert body["cnpj"] == "00.000.000/0001-00"


def test_profile_activity_defaults_and_updates(client):
    created = client.post("/api/profiles", json={"name": "MEI", "kind": "business"}).get_json()
    assert created["activity"] == "servicos"
    res = client.put(f"/api/profiles/{created['id']}", json={
        "name": "MEI", "kind": "business", "activity": "comercio",
    })
    assert res.status_code == 200
    assert res.get_json()["activity"] == "comercio"


def test_profile_activity_invalid_rejected(client):
    res = client.post("/api/profiles", json={
        "name": "MEI", "kind": "business", "activity": "pesca",
    })
    assert res.status_code == 400


def test_repository_scopes_by_profile(tmp_path):
    engine = connect(tmp_path / "p.sqlite")
    init_db(engine)
    session = make_session(engine)
    repo = Repository(session)
    p1 = repo.add_profile(Profile(name="A", kind="personal"))
    p2 = repo.add_profile(Profile(name="B", kind="business"))

    r1 = Repository(session, p1.id)
    r2 = Repository(session, p2.id)
    r1.add_account(Account(name="Conta A", type="bank"))
    r2.add_account(Account(name="Conta B", type="bank"))

    assert [a.name for a in r1.list_accounts()] == ["Conta A"]
    assert [a.name for a in r2.list_accounts()] == ["Conta B"]
