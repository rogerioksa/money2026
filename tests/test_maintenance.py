from __future__ import annotations

import io
from pathlib import Path


def _login(client) -> None:
    res = client.post("/api/auth/login", json={"username": "tester", "password": "senha123"})
    assert res.status_code == 200


def _create_account(client, name: str) -> dict:
    res = client.post("/api/accounts", json={
        "name": name, "type": "bank", "initial_balance": 1000,
    })
    assert res.status_code == 201
    return res.get_json()


def _backup(client) -> dict:
    res = client.post("/api/maintenance/backup")
    assert res.status_code == 201
    return res.get_json()["backup"]


def test_backup_list_and_download(client):
    backup = _backup(client)
    path = Path(backup["path"])
    assert path.is_file()
    assert path.parent.name == "backups"
    assert path.read_bytes()[:16] == b"SQLite format 3\x00"

    listing = client.get("/api/maintenance/backups")
    assert listing.status_code == 200
    data = listing.get_json()
    assert data["database"].endswith("money99.sqlite")
    assert any(item["name"] == backup["name"] for item in data["backups"])

    download = client.get(f"/api/maintenance/backups/{backup['name']}")
    assert download.status_code == 200
    assert download.data[:16] == b"SQLite format 3\x00"
    assert "attachment" in download.headers["Content-Disposition"]


def test_restore_backup_reverts_changes(client):
    _create_account(client, "Conta antiga")
    backup = _backup(client)
    _create_account(client, "Conta nova")

    res = client.post(
        f"/api/maintenance/backups/{backup['name']}/restore",
        json={"confirm": "RESTAURAR"},
    )
    assert res.status_code == 200
    assert res.get_json()["relogin"] is True

    _login(client)
    accounts = client.get("/api/accounts").get_json()
    assert [account["name"] for account in accounts] == ["Conta antiga"]
    # Backup automático de segurança antes de substituir o banco.
    assert res.get_json()["backup"] is not None


def test_restore_upload(client):
    _create_account(client, "Original")
    backup = _backup(client)
    payload = Path(backup["path"]).read_bytes()
    _create_account(client, "Descartada")

    res = client.post("/api/maintenance/restore", data={
        "file": (io.BytesIO(payload), "copia.sqlite"),
        "confirm": "RESTAURAR",
    })
    assert res.status_code == 200

    _login(client)
    accounts = client.get("/api/accounts").get_json()
    assert [account["name"] for account in accounts] == ["Original"]


def test_restore_requires_confirmation_and_valid_file(client):
    _create_account(client, "Mantida")

    bad_confirm = client.post("/api/maintenance/restore", data={
        "file": (io.BytesIO(b"x"), "copia.sqlite"),
        "confirm": "nao",
    })
    assert bad_confirm.status_code == 400

    invalid = client.post("/api/maintenance/restore", data={
        "file": (io.BytesIO(b"isto nao e um sqlite"), "copia.sqlite"),
        "confirm": "RESTAURAR",
    })
    assert invalid.status_code == 400

    # Sessão e dados permanecem intactos após falhas de validação.
    accounts = client.get("/api/accounts").get_json()
    assert [account["name"] for account in accounts] == ["Mantida"]


def test_download_rejects_path_traversal(client):
    res = client.get("/api/maintenance/backups/..%2Fmoney99.sqlite")
    assert res.status_code == 404


def test_reset_database(client):
    _create_account(client, "Some no reset")

    denied = client.post("/api/maintenance/reset", json={"confirm": "apagar tudo"})
    assert denied.status_code == 400

    res = client.post("/api/maintenance/reset", json={"confirm": "APAGAR"})
    assert res.status_code == 200
    assert res.get_json()["relogin"] is True
    assert res.get_json()["backup"] is not None

    status = client.get("/api/auth/status").get_json()
    assert status["has_user"] is False

    setup = client.post("/api/auth/setup", json={"username": "novo", "password": "senha123"})
    assert setup.status_code == 201
    assert client.get("/api/accounts").get_json() == []
