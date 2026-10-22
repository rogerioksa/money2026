"""Blueprint de consulta de CNPJ."""

from __future__ import annotations

from flask import Blueprint, jsonify

from money99.api._common import error
from money99.services.cnpj import CnpjLookupError, fetch_cnpj

bp = Blueprint("cnpj", __name__, url_prefix="/api/cnpj")


@bp.get("/<cnpj>")
def lookup_cnpj(cnpj: str):
    try:
        return jsonify(fetch_cnpj(cnpj))
    except ValueError as exc:
        return error(str(exc))
    except CnpjLookupError as exc:
        return error(str(exc), 502)
