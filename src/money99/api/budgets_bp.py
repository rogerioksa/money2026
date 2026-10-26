"""Blueprint de orçamentos (anual, dividido em 12 meses)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo
from money99.services.budget import (
    actual_by_account,
    annual_budget_report,
    budget_alerts,
    budget_report,
)

bp = Blueprint("budgets", __name__, url_prefix="/api/budgets")


@bp.get("")
def get_budget():
    repo = get_repo()
    try:
        year = request.args.get("year", type=int)
        month = request.args.get("month", type=int)
    except ValueError:
        return error("ano/mês inválidos")
    if year is None:
        return error("ano é obrigatório")
    if month is None:
        return jsonify(annual_budget_report(repo, year))
    if month < 1 or month > 12:
        return error("mês inválido")
    return jsonify(budget_report(repo, year, month))


@bp.put("")
def set_budget():
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        year = int(payload.get("year"))
        category_id = int(payload.get("category_id"))
    except (TypeError, ValueError):
        return error("campos year/category_id inválidos")
    annual_planned = payload.get("annual_planned", None)
    planned = payload.get("planned", None)
    if annual_planned is None and planned is not None:
        annual_planned = int(planned) * 12
    try:
        annual_planned = int(annual_planned or 0)
    except (TypeError, ValueError):
        return error("valor planejado inválido")
    if annual_planned < 0:
        return error("valor planejado deve ser positivo")
    try:
        repo.get_category(category_id)
    except LookupError as exc:
        return error(str(exc), 404)
    repo.set_annual_budget(year, category_id, annual_planned)
    return jsonify({"ok": True, "annual_planned": annual_planned})


@bp.get("/accounts")
def get_budget_accounts():
    repo = get_repo()
    try:
        year = request.args.get("year", type=int)
        month = request.args.get("month", type=int)
    except ValueError:
        return error("ano/mês inválidos")
    if year is None:
        return error("ano é obrigatório")
    return jsonify(actual_by_account(repo, year, month))


@bp.get("/alerts")
def get_budget_alerts():
    repo = get_repo()
    try:
        year = request.args.get("year", type=int)
        month = request.args.get("month", type=int)
    except ValueError:
        return error("ano/mês inválidos")
    if year is None or month is None:
        return error("ano e mês são obrigatórios")
    return jsonify(budget_alerts(repo, year, month))