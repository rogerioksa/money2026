"""Helpers compartilhados dos blueprints."""

from __future__ import annotations

from flask import current_app, jsonify

from money99.db.repository import Repository


def get_repo() -> Repository:
    return current_app.extensions["get_repo"]()


def error(message: str, status: int = 400):
    return jsonify({"error": message}), status
