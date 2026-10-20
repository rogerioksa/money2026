"""Registro dos blueprints Flask."""

from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from money99.api import (
        accounts_bp,
        budgets_bp,
        categories_bp,
        import_bp,
        reports_bp,
        transactions_bp,
    )

    app.register_blueprint(accounts_bp.bp)
    app.register_blueprint(categories_bp.bp)
    app.register_blueprint(transactions_bp.bp)
    app.register_blueprint(budgets_bp.bp)
    app.register_blueprint(reports_bp.bp)
    app.register_blueprint(import_bp.bp)
