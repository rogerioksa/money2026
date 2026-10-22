from __future__ import annotations

import pytest


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from money99.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def anon_client(app):
    """Cliente sem sessão (para testar o guard de autenticação)."""
    return app.test_client()


@pytest.fixture()
def client(app):
    """Cliente autenticado: cria o usuário local e faz login."""
    with app.test_client() as c:
        c.post("/api/auth/setup", json={"username": "tester", "password": "senha123"})
        yield c
