"""Blueprint de conciliação: sugestões de pares para revisão em lote."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo
from money99.services.reconcile import suggest_matches

bp = Blueprint("reconcile", __name__, url_prefix="/api/reconcile")


@bp.get("/suggestions")
def suggestions():
    account_id = request.args.get("account_id", type=int)
    if not account_id:
        return error("account_id obrigatório", 400)
    repo = get_repo()
    return jsonify(suggest_matches(repo, account_id))
