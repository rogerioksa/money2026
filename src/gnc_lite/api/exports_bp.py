"""Exportacoes salvas em arquivo (o webview nao trata download de blob)."""

from __future__ import annotations

import json
from datetime import date

from flask import Blueprint, g, jsonify, request

from gnc_lite.config import load_config
from gnc_lite.data_path import exports_dir, open_for_print
from gnc_lite.services import obligations

bp = Blueprint("exports", __name__, url_prefix="/api/exports")


def _safe_name(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1].strip()
    if not name or name in (".", ".."):
        raise ValueError("Nome de arquivo invalido.")
    return name


@bp.post("/das-csv")
def export_das_csv() -> tuple:
    """Salva a lista dos DAS do ano e devolve o caminho do arquivo."""
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"error": "no_company_open"}), 400
    payload = request.get_json(silent=True) or {}
    try:
        year = int(payload.get("year", date.today().year))
    except (TypeError, ValueError):
        return jsonify({"error": "Ano invalido."}), 400
    records = obligations.load_records(web.company.db_path)
    text = obligations.das_csv_text(web.ledger, load_config(), year, records, date.today())
    target = exports_dir() / f"DAS_{year}_situacao.csv"
    target.write_text(text, encoding="utf-8")
    return jsonify({"ok": True, "filename": target.name, "path": str(target)})


@bp.post("/cnpj-ficha")
def export_cnpj_ficha() -> tuple:
    """Salva a ficha cadastral (cache Minha Receita) em JSON."""
    from gnc_lite.services import cnpj

    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"error": "no_company_open"}), 400
    payload = request.get_json(silent=True) or {}
    raw = str(payload.get("cnpj") or "") or "".join(
        ch for ch in (load_config().mei_cnpj or "") if ch.isdigit()
    )
    try:
        digits = cnpj.normalize(raw)
    except cnpj.CnpjError as exc:
        return jsonify({"error": str(exc)}), 400
    cached = cnpj.load_cache(web.company.db_path)
    if cached is None or cached.get("cnpj") != digits:
        try:
            result = cnpj.summarize(cnpj.lookup(digits))
        except cnpj.CnpjError as exc:
            return jsonify({"error": str(exc)}), 502
        cached = cnpj.save_cache(web.company.db_path, digits, result)
    target = exports_dir() / f"CNPJ_{digits}_ficha.json"
    target.write_text(
        json.dumps(cached, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return jsonify({"ok": True, "filename": target.name, "path": str(target)})


@bp.get("/open")
def open_file() -> tuple:
    """Abre um arquivo da pasta de exportacoes no programa padrao."""
    filename = request.args.get("file", "")
    try:
        name = _safe_name(filename)
    except ValueError:
        return jsonify({"error": "Nome de arquivo invalido."}), 400
    target = exports_dir() / name
    if not target.exists():
        return jsonify({"error": "Arquivo nao encontrado."}), 404
    try:
        open_for_print(target)
    except Exception as exc:  # noqa: BLE001 - informa sem quebrar a tela
        return jsonify({"error": f"Nao foi possivel abrir: {exc}"}), 500
    return jsonify({"ok": True})
