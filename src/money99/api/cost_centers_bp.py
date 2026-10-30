"""Blueprint de centros de custo."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo
from money99.domain.cost_center import CostCenter

bp = Blueprint("cost_centers", __name__, url_prefix="/api/cost-centers")


def _serialize(cc):
    return {"id": cc.id, "name": cc.name, "active": cc.active}


@bp.get("")
def list_cost_centers():
    repo = get_repo()
    active_only = request.args.get("active_only") == "1"
    return jsonify([_serialize(c) for c in repo.list_cost_centers(active_only=active_only)])


@bp.post("")
def create_cost_center():
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        cc = CostCenter(name=str(payload.get("name", "")), active=bool(payload.get("active", True)))
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    created = repo.add_cost_center(cc)
    return jsonify(_serialize(created)), 201


@bp.put("/<int:cc_id>")
def update_cost_center(cc_id: int):
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        existing = repo.get_cost_center(cc_id)
    except LookupError as exc:
        return error(str(exc), 404)
    cc = CostCenter(
        id=cc_id,
        name=str(payload.get("name", existing.name)),
        active=bool(payload.get("active", existing.active)),
    )
    try:
        updated = repo.update_cost_center(cc)
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(_serialize(updated))


@bp.delete("/<int:cc_id>")
def delete_cost_center(cc_id: int):
    repo = get_repo()
    try:
        repo.delete_cost_center(cc_id)
    except LookupError as exc:
        return error(str(exc), 404)
    return jsonify({"ok": True})