"""Backup, restauração e reset do banco de dados (Configurações)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, request, send_file, session

from money99.data_path import backups_dir
from money99.services import maintenance

bp = Blueprint("maintenance", __name__, url_prefix="/api/maintenance")

_MAX_UPLOAD = 64 * 1024 * 1024


def _database_path() -> str:
    return current_app.config["DB_PATH"]


def _engine():
    return current_app.config["ENGINE"]


def _backup_file(name: str) -> Path:
    if not name or Path(name).name != name or not name.endswith(maintenance.BACKUP_SUFFIX):
        abort(404)
    path = backups_dir() / name
    if not path.is_file():
        abort(404)
    return path


def _error(message: str, status: int = 400):
    return jsonify({"error": message}), status


@bp.get("/backups")
def list_backups():
    return jsonify({
        "database": str(Path(_database_path()).resolve()),
        "backups": maintenance.list_backups(),
    })


@bp.post("/backup")
def create_backup():
    try:
        backup = maintenance.make_backup(_database_path())
    except maintenance.MaintenanceError as exc:
        return _error(str(exc))
    return jsonify({"ok": True, "backup": backup}), 201


@bp.get("/backups/<name>")
def download_backup(name: str):
    path = _backup_file(name)
    return send_file(
        path,
        as_attachment=True,
        download_name=name,
        mimetype="application/x-sqlite3",
    )


@bp.post("/backups/<name>/restore")
def restore_backup(name: str):
    path = _backup_file(name)
    data = request.get_json(silent=True) or {}
    if str(data.get("confirm", "")).strip().upper() != "RESTAURAR":
        return _error('digite "RESTAURAR" para confirmar')
    try:
        result = maintenance.restore_database(_database_path(), path, _engine())
    except maintenance.MaintenanceError as exc:
        return _error(str(exc))
    session.clear()
    return jsonify(result)


@bp.post("/restore")
def restore_upload():
    if request.content_length and request.content_length > _MAX_UPLOAD:
        return _error("arquivo muito grande (limite de 64 MB)", 413)
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return _error("selecione um arquivo de backup")
    if str(request.form.get("confirm", "")).strip().upper() != "RESTAURAR":
        return _error('digite "RESTAURAR" para confirmar')

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, dir=backups_dir(), suffix=".upload.sqlite"
        ) as temp:
            temp_path = Path(temp.name)
        upload.save(temp_path)
        maintenance.validate_backup(temp_path)
        result = maintenance.restore_database(_database_path(), temp_path, _engine())
    except maintenance.MaintenanceError as exc:
        return _error(str(exc))
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    session.clear()
    return jsonify(result)


@bp.post("/reset")
def reset():
    data = request.get_json(silent=True) or {}
    if str(data.get("confirm", "")).strip().upper() != "APAGAR":
        return _error('digite "APAGAR" para confirmar')
    try:
        result = maintenance.reset_database(_database_path(), _engine())
    except maintenance.MaintenanceError as exc:
        return _error(str(exc))
    session.clear()
    return jsonify(result)
