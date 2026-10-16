from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from gnc_lite.config import load_config
from gnc_lite.services import cnpj

bp = Blueprint("cnpj", __name__, url_prefix="/api/cnpj")


def _configured_cnpj() -> str:
    return "".join(ch for ch in (load_config().mei_cnpj or "") if ch.isdigit())


@bp.get("/status")
def status() -> tuple:
    """Situacao em cache + se esta desatualizada. Com ?auto=1, atualiza se obsoleto."""
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"error": "no_company_open"}), 400
    digits = _configured_cnpj()
    if not digits:
        return jsonify({"configured": False})
    cached = cnpj.load_cache(web.company.db_path)
    stale = cnpj.is_stale(cached, digits)
    if request.args.get("auto") == "1" and stale:
        try:
            result = cnpj.summarize(cnpj.lookup(digits))
            cached = cnpj.save_cache(web.company.db_path, digits, result)
            stale = False
        except cnpj.CnpjError as exc:
            return jsonify(
                {"configured": True, "cnpj": digits, "cached": cached,
                 "stale": True, "error": str(exc)}
            )
    return jsonify({"configured": True, "cnpj": digits, "cached": cached, "stale": stale})


@bp.post("/check")
def check() -> tuple:
    """Forca uma consulta agora (CNPJ do cadastro ou informado)."""
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    raw = str(payload.get("cnpj") or "") or _configured_cnpj()
    try:
        digits = cnpj.normalize(raw)
    except cnpj.CnpjError as exc:
        return jsonify({"error": str(exc)}), 400
    try:
        result = cnpj.summarize(cnpj.lookup(digits))
    except cnpj.CnpjError as exc:
        return jsonify({"error": str(exc)}), 502
    cached = cnpj.save_cache(web.company.db_path, digits, result)
    return jsonify({"ok": True, "cached": cached})


@bp.post("/fill")
def fill() -> tuple:
    """Devolve os campos do cadastro MEI preenchidos com dados da Receita.

    Nao salva nada: o frontend mostra nos inputs e o usuario confirma em Salvar.
    """
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    raw = str(payload.get("cnpj") or "") or _configured_cnpj()
    try:
        digits = cnpj.normalize(raw)
    except cnpj.CnpjError as exc:
        return jsonify({"error": str(exc)}), 400
    try:
        result = cnpj.summarize(cnpj.lookup(digits))
    except cnpj.CnpjError as exc:
        return jsonify({"error": str(exc)}), 502
    cnpj.save_cache(web.company.db_path, digits, result)
    warnings: list[str] = []
    if result.get("opcao_mei") is False:
        warnings.append("CNPJ não optante pelo MEI na Receita Federal.")
    municipio = str(result.get("municipio") or "")
    fields = {
        "nome_empresarial": str(result.get("razao_social") or ""),
        "cnpj": cnpj.format_cnpj(digits),
        "atividade": str(result.get("cnae_descricao") or ""),
        "municipio": municipio.title() if municipio else "",
        "uf": str(result.get("uf") or ""),
        "inicio_atividade": str(result.get("data_inicio_atividade") or ""),
    }
    filled = sorted(key for key, value in fields.items() if value)
    return jsonify({"ok": True, "fields": fields, "filled": filled, "warnings": warnings})
