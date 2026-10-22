"""Blueprint de relatórios do MEI (perfil empresarial)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo
from money99.services.mei import monthly_caderno, monthly_report, period_report

bp = Blueprint("mei", __name__, url_prefix="/api/mei")


@bp.get("/report")
def report():
    repo = get_repo()
    year = request.args.get("year")
    if not year or not year.isdigit():
        return error("year é obrigatório")
    if repo.profile_id is None:
        return error("nenhum perfil ativo", 400)
    return jsonify(monthly_report(repo, int(year)))


@bp.get("/caderno")
def caderno():
    repo = get_repo()
    year = request.args.get("year")
    month = request.args.get("month")
    if not year or not year.isdigit():
        return error("year é obrigatório")
    if not month or not month.isdigit():
        return error("month é obrigatório")
    if repo.profile_id is None:
        return error("nenhum perfil ativo", 400)
    try:
        data = monthly_caderno(repo, int(year), int(month))
    except ValueError as exc:
        return error(str(exc))
    return jsonify(data)


@bp.get("/period")
def period():
    repo = get_repo()
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return error("start e end são obrigatórios")
    return jsonify(period_report(repo, start, end))
