from __future__ import annotations

from datetime import date

from flask import Blueprint, g, jsonify, request

from gnc_lite.config import AppConfig, Profile, load_config, save_config
from gnc_lite.domain.money import Money

bp = Blueprint("config", __name__, url_prefix="/api/config")


def _serialize(config: AppConfig) -> dict:
    return {
        "profile": config.profile.value,
        "profile_label": config.profile.label,
        "mei": {
            "nome_empresarial": config.mei_nome_empresarial,
            "cnpj": config.mei_cnpj,
            "atividade": config.mei_atividade,
            "municipio": config.mei_municipio,
            "uf": config.mei_uf,
            "inicio_atividade": (
                config.mei_inicio_atividade.isoformat()
                if config.mei_inicio_atividade
                else ""
            ),
            "limite_anual_minor": config.mei_limite_anual.minor_units,
        },
    }


@bp.get("")
def get_config() -> tuple:
    return jsonify(_serialize(load_config()))


@bp.put("")
def put_config() -> tuple:
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    config = load_config()
    if "profile" in payload:
        try:
            config.profile = Profile(str(payload["profile"]))
        except ValueError:
            return jsonify({"error": "Perfil invalido."}), 400
    mei = payload.get("mei") or {}
    for attr, key in (
        ("mei_nome_empresarial", "nome_empresarial"),
        ("mei_cnpj", "cnpj"),
        ("mei_atividade", "atividade"),
        ("mei_municipio", "municipio"),
        ("mei_uf", "uf"),
    ):
        if key in mei:
            setattr(config, attr, str(mei[key] or ""))
    if "inicio_atividade" in mei:
        raw = str(mei["inicio_atividade"] or "")
        if raw:
            try:
                config.mei_inicio_atividade = date.fromisoformat(raw)
            except ValueError:
                return jsonify({"error": "Data de inicio invalida."}), 400
        else:
            config.mei_inicio_atividade = None
    if "limite_anual_minor" in mei:
        try:
            minor = int(mei["limite_anual_minor"])
        except (TypeError, ValueError):
            return jsonify({"error": "Limite invalido."}), 400
        if minor <= 0:
            return jsonify({"error": "Limite deve ser positivo."}), 400
        config.mei_limite_anual = Money(minor, config.mei_limite_anual.currency)
    save_config(config)
    return jsonify({"ok": True, "config": _serialize(config)})
