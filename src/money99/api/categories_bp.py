"""Blueprint de categorias."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo

bp = Blueprint("categories", __name__, url_prefix="/api/categories")


def _serialize(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "parent_id": row.parent_id,
    }


@bp.get("")
def list_categories():
    repo = get_repo()
    kind = request.args.get("kind")
    return jsonify([_serialize(c) for c in repo.list_categories(kind=kind)])


@bp.post("")
def create_category():
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        row = repo.add_category(
            name=payload.get("name", "").strip(),
            kind=payload.get("kind", ""),
            parent_id=payload.get("parent_id"),
        )
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(_serialize(row)), 201
