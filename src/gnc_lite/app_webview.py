"""Backend Flask + launcher pywebview (interface web local).

Nao depende do Flet: abre o livro SQLite direto via Ledger/Repository e expoe
uma API REST consumida pelo frontend em ``web/``. O servidor escuta apenas em
127.0.0.1 (uso desktop local).
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Flask, g, jsonify, render_template, request

from gnc_lite.api import (
    accounts_bp,
    auth_bp,
    cnpj_bp,
    companies_bp,
    config_bp,
    exports_bp,
    import_bp,
    invoices_bp,
    obligations_bp,
    reports_bp,
    transactions_bp,
    users_bp,
)
from gnc_lite.db.chart import CHART_BUSINESS
from gnc_lite.db.repository import Repository
from gnc_lite.db.session import connect, init_db, make_session
from gnc_lite.services import companies
from gnc_lite.services.ledger import Ledger


def _resource_base() -> Path:
    """Pasta ``gnc_lite`` (congelado: dentro de ``sys._MEIPASS``)."""
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        return Path(frozen) / "gnc_lite"
    return Path(__file__).resolve().parent


@dataclass
class WebSession:
    """Empresa aberta: livro + sessao de banco + usuario logado."""

    company: companies.Company
    ledger: Ledger
    dbsession: Any
    user: Any | None = None

    @property
    def can_write(self) -> bool:
        if self.user is None:
            return True
        try:
            return bool(self.user.role.can_write)
        except Exception:  # noqa: BLE001 - papel inesperado libera como antes
            return True

    @property
    def is_admin(self) -> bool:
        if self.user is None:
            return False
        try:
            return bool(self.user.role.is_admin)
        except Exception:  # noqa: BLE001
            return False


def open_ledger(db_path: str, chart: str = CHART_BUSINESS) -> tuple[Ledger, Any]:
    """Abre (ou cria) o livro e garante o plano de contas."""
    engine = connect(db_path)
    init_db(engine)
    session = make_session(engine)()
    repo = Repository(session)
    ledger = Ledger(repo)
    if repo.account_count() == 0:
        ledger.seed_default_chart(chart)
        session.commit()
    return ledger, session


def create_app() -> Flask:
    base = _resource_base()
    app = Flask(
        __name__,
        static_folder=str(base / "web" / "static"),
        template_folder=str(base / "web" / "templates"),
    )
    app.config["COMPANY_ID"] = None
    app.config["SESSION"] = None
    app.config["USER_ID"] = None

    def _resolve_user(ledger: Ledger) -> Any | None:
        user_id = app.config.get("USER_ID")
        if user_id is None:
            return None
        try:
            return ledger.repo.get_user(int(user_id))
        except Exception:  # noqa: BLE001 - banco em transicao nao pode travar request
            return None

    def current_session() -> WebSession | None:
        registry = companies.CompanyRegistry()
        items = registry.list()
        if not items:
            return None
        wanted = app.config.get("COMPANY_ID")
        company = registry.get(wanted) if wanted else None
        if company is None:
            company = items[0]
        sess: WebSession | None = app.config.get("SESSION")
        if sess is None or sess.company.id != company.id or sess.company.db_path != company.db_path:
            if sess is not None:
                try:
                    sess.dbsession.close()
                except Exception:  # noqa: BLE001 - troca de empresa nao pode travar
                    pass
            ledger, dbsession = open_ledger(company.db_path)
            sess = WebSession(company, ledger, dbsession, _resolve_user(ledger))
            app.config["SESSION"] = sess
            app.config["COMPANY_ID"] = company.id
        elif sess.user is None and app.config.get("USER_ID") is not None:
            sess.user = _resolve_user(sess.ledger)
        return sess

    @app.before_request
    def _load_session() -> None:
        if request.endpoint == "static":
            return
        g.web = current_session()

    app.register_blueprint(companies_bp.bp)
    app.register_blueprint(accounts_bp.bp)
    app.register_blueprint(transactions_bp.bp)
    app.register_blueprint(import_bp.bp)
    app.register_blueprint(reports_bp.bp)
    app.register_blueprint(invoices_bp.bp)
    app.register_blueprint(auth_bp.bp)
    app.register_blueprint(users_bp.bp)
    app.register_blueprint(config_bp.bp)
    app.register_blueprint(obligations_bp.bp)
    app.register_blueprint(cnpj_bp.bp)
    app.register_blueprint(exports_bp.bp)

    @app.get("/")
    def index() -> Any:
        return render_template("base.html")

    @app.errorhandler(400)
    def _400(error: Any) -> Any:
        description = getattr(error, "description", None) or str(error)
        return jsonify({"error": str(description)}), 400

    @app.errorhandler(404)
    def _404(_error: Any) -> Any:
        return jsonify({"error": "not_found"}), 404

    @app.errorhandler(500)
    def _500(_error: Any) -> Any:
        return jsonify({"error": "internal_error"}), 500

    return app


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_webview() -> None:
    import webview  # type: ignore[import-untyped]

    app = create_app()
    port = _get_free_port()

    def start_flask() -> None:
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=False)

    thread = threading.Thread(target=start_flask, daemon=True)
    thread.start()
    for _ in range(100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect(("127.0.0.1", port))
                break
        except OSError:
            time.sleep(0.1)
    webview.create_window("Money 26", f"http://127.0.0.1:{port}/", width=1280, height=900)
    webview.start()


if __name__ == "__main__":
    run_webview()
