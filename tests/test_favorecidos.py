"""Blueprint de favorecidos (clientes/fornecedores): CRUD e guarda de rotas."""

from __future__ import annotations


def test_list_favorecidos_empty(client):
    res = client.get("/api/favorecidos")
    assert res.status_code == 200
    assert res.get_json() == []


def test_create_favorecido(client):
    res = client.post(
        "/api/favorecidos",
        json={"name": "ACME", "kind": "supplier", "document": "123"},
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["name"] == "ACME"
    assert body["kind"] == "supplier"
    assert body["id"] is not None


def test_create_favorecido_requires_name(client):
    res = client.post("/api/favorecidos", json={"name": "  "})
    assert res.status_code == 400


def test_update_favorecido(client):
    created = client.post("/api/favorecidos", json={"name": "ACME"}).get_json()
    res = client.put(
        f"/api/favorecidos/{created['id']}",
        json={"name": "ACME Ltda", "active": False},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["name"] == "ACME LTDA"
    assert body["active"] is False


def test_update_favorecido_not_found(client):
    res = client.put("/api/favorecidos/999", json={"name": "X"})
    assert res.status_code == 404


def test_delete_favorecido(client):
    created = client.post("/api/favorecidos", json={"name": "ACME"}).get_json()
    res = client.delete(f"/api/favorecidos/{created['id']}")
    assert res.status_code == 200
    assert client.get("/api/favorecidos").get_json() == []


def test_delete_favorecido_not_found(client):
    res = client.delete("/api/favorecidos/999")
    assert res.status_code == 404


def test_active_only_filter(client):
    client.post("/api/favorecidos", json={"name": "A", "active": True})
    client.post("/api/favorecidos", json={"name": "B", "active": False})
    res = client.get("/api/favorecidos?active_only=1")
    assert res.status_code == 200
    names = [f["name"] for f in res.get_json()]
    assert names == ["A"]


def test_favorecidos_requires_login(anon_client):
    assert anon_client.get("/api/favorecidos").status_code == 401
    assert anon_client.post("/api/favorecidos", json={"name": "X"}).status_code == 401
