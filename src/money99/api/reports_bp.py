"""Blueprint de relatórios."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo
from money99.services.reports import (
    cash_flow,
    cash_flow_forecast,
    dashboard,
    net_worth,
    spending_by_category,
)

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@bp.get("/dashboard")
def dashboard_report():
    return jsonify(dashboard(get_repo()))


@bp.get("/spending")
def spending():
    repo = get_repo()
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return error("start e end são obrigatórios")
    kind = request.args.get("kind", "expense")
    if kind not in ("income", "expense"):
        return error("kind inválido")
    return jsonify(spending_by_category(repo, start, end, kind))


@bp.get("/net-worth")
def net_worth_report():
    repo = get_repo()
    return jsonify(net_worth(repo, request.args.get("as_of")))


@bp.get("/cash-flow")
def cash_flow_report():
    repo = get_repo()
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return error("start e end são obrigatórios")
    return jsonify(cash_flow(repo, start, end))


@bp.get("/forecast")
def forecast_report():
    repo = get_repo()
    try:
        months = int(request.args.get("months", 12))
    except ValueError:
        return error("months inválido")
    return jsonify(cash_flow_forecast(repo, months))
