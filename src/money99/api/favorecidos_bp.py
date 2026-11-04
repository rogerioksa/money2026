"""Blueprint de favorecidos (clientes/fornecedores)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo
from money99.domain.favorecido import Favorecido

bp = Blueprint("favorecidos", __name__, url_prefix="/api/favorecidos")


def _serialize(fav):
    return {
        "id": fav.id,
        "name": fav.name,
        "kind": fav.kind,
        "document": fav.document,
        "phone": fav.phone,
        "email": fav.email,
        "notes": fav.notes,
        "active": fav.active,
    }


@bp.get("")
def list_favorecidos():
    repo = get_repo()
    active_only = request.args.get("active_only") == "1"
    return jsonify([_serialize(f) for f in repo.list_favorecidos(active_only=active_only)])


@bp.post("")
def create_favorecido():
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        fav = Favorecido(
            name=str(payload.get("name", "")),
            kind=str(payload.get("kind", "supplier") or "supplier"),
            document=str(payload.get("document", "") or ""),
            phone=str(payload.get("phone", "") or ""),
            email=str(payload.get("email", "") or ""),
            notes=str(payload.get("notes", "") or ""),
            active=bool(payload.get("active", True)),
        )
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    created = repo.add_favorecido(fav)
    return jsonify(_serialize(created)), 201


@bp.put("/<int:favorecido_id>")
def update_favorecido(favorecido_id: int):
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        existing = repo.get_favorecido(favorecido_id)
    except LookupError as exc:
        return error(str(exc), 404)
    fav = Favorecido(
        id=favorecido_id,
        name=str(payload.get("name", existing.name)),
        kind=str(payload.get("kind", existing.kind) or existing.kind),
        document=str(payload.get("document", existing.document) or ""),
        phone=str(payload.get("phone", existing.phone) or ""),
        email=str(payload.get("email", existing.email) or ""),
        notes=str(payload.get("notes", existing.notes) or ""),
        active=bool(payload.get("active", existing.active)),
    )
    try:
        updated = repo.update_favorecido(fav)
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(_serialize(updated))


@bp.delete("/<int:favorecido_id>")
def delete_favorecido(favorecido_id: int):
    repo = get_repo()
    try:
        repo.delete_favorecido(favorecido_id)
    except LookupError as exc:
        return error(str(exc), 404)
    return jsonify({"ok": True})