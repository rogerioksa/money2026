"""Registro dos blueprints Flask."""

from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from money99.api import (
        accounts_bp,
        auth_bp,
        budgets_bp,
        categories_bp,
        cnpj_bp,
        favorecidos_bp,
        import_bp,
        maintenance_bp,
        mei_bp,
        profiles_bp,
        reports_bp,
        titles_bp,
        transactions_bp,
    )

    app.register_blueprint(auth_bp.bp)
    app.register_blueprint(profiles_bp.bp)
    app.register_blueprint(cnpj_bp.bp)
    app.register_blueprint(accounts_bp.bp)
    app.register_blueprint(categories_bp.bp)
    app.register_blueprint(transactions_bp.bp)
    app.register_blueprint(titles_bp.bp)
    app.register_blueprint(favorecidos_bp.bp)
    app.register_blueprint(budgets_bp.bp)
    app.register_blueprint(reports_bp.bp)
    app.register_blueprint(import_bp.bp)
    app.register_blueprint(mei_bp.bp)
    app.register_blueprint(maintenance_bp.bp)
