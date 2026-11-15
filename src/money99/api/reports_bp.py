"""Blueprint de relatórios."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo
from money99.services.insights import dashboard_insights
from money99.services.reports import (
    cash_flow,
    cash_flow_forecast,
    dashboard,
    delinquency_by_favorecido,
    income_statement,
    net_worth,
    spending_by_account,
    spending_by_category,
    spending_by_cost_center,
)

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@bp.get("/dashboard")
def dashboard_report():
    repo = get_repo()
    today = date.today()
    year = request.args.get("year", default=today.year, type=int)
    month = request.args.get("month", default=today.month, type=int)
    if year is None or not (2000 <= year <= 2200):
        year = today.year
    if month is None or not (1 <= month <= 12):
        month = today.month

    data = dashboard(repo)
    insights = dashboard_insights(repo, year, month, data)
    data["credit"].update(insights.pop("credit"))
    data.update(insights)
    return jsonify(data)


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


@bp.get("/income-statement")
def income_statement_report():
    repo = get_repo()
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return error("start e end são obrigatórios")
    return jsonify(income_statement(repo, start, end))


@bp.get("/by-cost-center")
def by_cost_center_report():
    repo = get_repo()
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return error("start e end são obrigatórios")
    return jsonify(spending_by_cost_center(repo, start, end))


@bp.get("/forecast")
def forecast_report():
    repo = get_repo()
    try:
        months = int(request.args.get("months", 12))
    except ValueError:
        return error("months inválido")
    return jsonify(cash_flow_forecast(repo, months))


@bp.get("/delinquency")
def delinquency_report():
    repo = get_repo()
    return jsonify(delinquency_by_favorecido(repo))


@bp.get("/by-account")
def by_account_report():
    repo = get_repo()
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return error("start e end são obrigatórios")
    return jsonify(spending_by_account(repo, start, end))
