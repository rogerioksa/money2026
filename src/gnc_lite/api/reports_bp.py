from __future__ import annotations

from datetime import date

from flask import Blueprint, g, jsonify, request

from gnc_lite.config import load_config
from gnc_lite.domain.money import Money
from gnc_lite.services import mei, reports

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def _cell(value: object) -> dict:
    if isinstance(value, Money):
        return {"text": f"{value.amount:,.2f}", "minor": value.minor_units}
    if value is None:
        return {"text": "", "minor": None}
    return {"text": str(value), "minor": None}


def _serialize(report: reports.Report) -> dict:
    return {
        "title": report.title,
        "columns": list(report.columns),
        "rows": [[_cell(v) for v in row] for row in report.rows],
        "footer": [_cell(v) for v in report.footer] if report.footer is not None else None,
        "period": report.period,
        "info": [{"label": label, "value": value} for label, value in report.info],
        "notes": list(report.notes),
    }


def _date_param(name: str) -> date | None:
    raw = request.args.get(name)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


@bp.get("/status")
def status() -> tuple:
    return jsonify({"ok": True})


@bp.get("/trial-balance")
def trial_balance() -> tuple:
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"error": "no_company_open"}), 400
    return jsonify(_serialize(reports.trial_balance(web.ledger)))


@bp.get("/income")
def income() -> tuple:
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"error": "no_company_open"}), 400
    report = reports.income_statement(web.ledger, _date_param("start"), _date_param("end"))
    return jsonify(_serialize(report))


@bp.get("/balance-sheet")
def balance_sheet() -> tuple:
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"error": "no_company_open"}), 400
    return jsonify(_serialize(reports.balance_sheet(web.ledger, _date_param("asof"))))


@bp.get("/cash-flow")
def cash_flow() -> tuple:
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"error": "no_company_open"}), 400
    report = reports.cash_flow(web.ledger, _date_param("start"), _date_param("end"))
    return jsonify(_serialize(report))


@bp.get("/mei-monthly")
def mei_monthly() -> tuple:
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"error": "no_company_open"}), 400
    try:
        year = int(request.args.get("year", date.today().year))
        month = int(request.args.get("month", date.today().month))
    except (TypeError, ValueError):
        return jsonify({"error": "Ano/mes invalidos."}), 400
    if not 1 <= month <= 12:
        return jsonify({"error": "Mes invalido."}), 400
    report = mei.billing_report(web.ledger, load_config(), year, month)
    return jsonify(_serialize(report))


@bp.get("/mei-annual")
def mei_annual() -> tuple:
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"error": "no_company_open"}), 400
    try:
        year = int(request.args.get("year", date.today().year))
    except (TypeError, ValueError):
        return jsonify({"error": "Ano invalido."}), 400
    report = mei.annual_report(web.ledger, load_config(), year)
    return jsonify(_serialize(report))
