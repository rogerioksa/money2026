"""Blueprint de orçamentos."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo
from money99.services.budget import budget_report

bp = Blueprint("budgets", __name__, url_prefix="/api/budgets")


@bp.get("")
def get_budget():
    repo = get_repo()
    try:
        year = request.args.get("year", type=int)
        month = request.args.get("month", type=int)
    except ValueError:
        return error("ano/mês inválidos")
    if year is None or month is None:
        return error("ano e mês são obrigatórios")
    return jsonify(budget_report(repo, year, month))


@bp.put("")
def set_budget():
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        year = int(payload.get("year"))
        month = int(payload.get("month"))
        category_id = int(payload.get("category_id"))
        planned = int(payload.get("planned", 0))
    except (TypeError, ValueError):
        return error("campos year/month/category_id/planned inválidos")
    if planned < 0:
        return error("valor planejado deve ser positivo")
    try:
        repo.get_category(category_id)
    except LookupError as exc:
        return error(str(exc), 404)
    repo.set_budget(year, month, category_id, planned)
    return jsonify({"ok": True})
