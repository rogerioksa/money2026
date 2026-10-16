from __future__ import annotations

from datetime import date

from flask import Blueprint, g, jsonify, request

from gnc_lite.config import load_config
from gnc_lite.services import obligations

bp = Blueprint("obligations", __name__, url_prefix="/api/obligations")


def _serialize(item: obligations.Obligation) -> dict:
    return {
        "key": item.key,
        "kind": item.kind,
        "title": item.title,
        "period": item.period,
        "due": item.due.isoformat(),
        "status": item.status,
        "detail": item.detail,
        "amount_minor": item.amount_minor,
    }


@bp.get("")
def list_obligations() -> tuple:
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"error": "no_company_open"}), 400
    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
    except (TypeError, ValueError):
        return jsonify({"error": "Ano/mes invalidos."}), 400
    if not 1 <= month <= 12:
        return jsonify({"error": "Mes invalido."}), 400
    items = obligations.compute(
        web.ledger, load_config(), year, month, web.company.db_path
    )
    return jsonify({"obligations": [_serialize(i) for i in items]})


@bp.post("/mark")
def mark() -> tuple:
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    key = str(payload.get("key") or "").strip()
    if not key or ":" not in key:
        return jsonify({"error": "Chave invalida."}), 400
    obligations.mark(web.company.db_path, key, bool(payload.get("done", True)))
    return jsonify({"ok": True})
