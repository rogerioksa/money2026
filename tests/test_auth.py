"""Autenticação: setup inicial, login, logout e guarda de rotas."""

from __future__ import annotations


def test_guard_redirects_spa_to_login(anon_client):
    res = anon_client.get("/")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_guard_blocks_api_unauthorized(anon_client):
    res = anon_client.get("/api/accounts")
    assert res.status_code == 401
    assert res.get_json()["error"]


def test_login_page_public(anon_client):
    from money99 import __version__

    res = anon_client.get("/login")
    assert res.status_code == 200
    assert b"Money 2026" in res.data
    assert f"Versão {__version__}".encode() in res.data


def test_status_before_setup(anon_client):
    body = anon_client.get("/api/auth/status").get_json()
    assert body == {"has_user": False, "authenticated": False, "username": None, "profile_id": None}


def test_setup_then_authenticated(anon_client):
    res = anon_client.post("/api/auth/setup", json={"username": "ana", "password": "segredo"})
    assert res.status_code == 201
    status = anon_client.get("/api/auth/status").get_json()
    assert status["has_user"] is True
    assert status["authenticated"] is True
    assert status["username"] == "ana"
    # SPA liberada após setup
    assert anon_client.get("/").status_code == 200


def test_setup_rejects_short_password(anon_client):
    res = anon_client.post("/api/auth/setup", json={"username": "ana", "password": "1"})
    assert res.status_code == 400


def test_setup_rejects_second_user(anon_client):
    anon_client.post("/api/auth/setup", json={"username": "ana", "password": "segredo"})
    res = anon_client.post("/api/auth/setup", json={"username": "bob", "password": "segredo"})
    assert res.status_code == 400


def test_login_wrong_password(anon_client):
    anon_client.post("/api/auth/setup", json={"username": "ana", "password": "segredo"})
    anon_client.post("/api/auth/logout")
    res = anon_client.post("/api/auth/login", json={"username": "ana", "password": "errada"})
    assert res.status_code == 401


def test_login_flow(anon_client):
    anon_client.post("/api/auth/setup", json={"username": "ana", "password": "segredo"})
    anon_client.post("/api/auth/logout")
    assert anon_client.get("/api/accounts").status_code == 401
    res = anon_client.post("/api/auth/login", json={"username": "ana", "password": "segredo"})
    assert res.status_code == 200
    assert anon_client.get("/api/accounts").status_code == 200


def test_logout_clears_session(anon_client):
    anon_client.post("/api/auth/setup", json={"username": "ana", "password": "segredo"})
    anon_client.post("/api/auth/logout")
    assert anon_client.get("/api/accounts").status_code == 401
    assert anon_client.get("/api/auth/status").get_json()["authenticated"] is False


def test_password_hash_roundtrip():
    from money99.services.auth import hash_password, verify_password

    stored, salt = hash_password("segredo!")
    assert "segredo!" not in stored
    assert verify_password("segredo!", stored, salt)
    assert not verify_password("errada", stored, salt)


def test_password_hash_rejects_malformed():
    from money99.services.auth import verify_password

    assert not verify_password("x", "lixo", "salt")
    assert not verify_password("x", "", "")


def test_change_password_flow(anon_client):
    anon_client.post("/api/auth/setup", json={"username": "ana", "password": "segredo"})
    # senha atual errada
    res = anon_client.post("/api/auth/change-password",
                           json={"current_password": "errada", "new_password": "novasenha"})
    assert res.status_code == 400
    # troca válida
    res = anon_client.post("/api/auth/change-password",
                           json={"current_password": "segredo", "new_password": "novasenha"})
    assert res.status_code == 200
    anon_client.post("/api/auth/logout")
    assert anon_client.post("/api/auth/login",
                            json={"username": "ana", "password": "segredo"}).status_code == 401
    assert anon_client.post("/api/auth/login",
                            json={"username": "ana", "password": "novasenha"}).status_code == 200


def test_change_password_rejects_short(anon_client):
    anon_client.post("/api/auth/setup", json={"username": "ana", "password": "segredo"})
    res = anon_client.post("/api/auth/change-password",
                           json={"current_password": "segredo", "new_password": "1"})
    assert res.status_code == 400
