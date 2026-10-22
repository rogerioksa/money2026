"""Helpers compartilhados dos blueprints."""

from __future__ import annotations

from flask import current_app, jsonify

from money99.db.repository import Repository


def get_repo(profile_id="__current__") -> Repository:
    """Repository no escopo do perfil atual (sessão) ou do perfil informado.

    Passe `profile_id=None` explicitamente para um repositório sem escopo.
    """
    return current_app.extensions["get_repo"](profile_id)


def error(message: str, status: int = 400):
    return jsonify({"error": message}), status
