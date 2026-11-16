"""Flask + launcher pywebview do Money 2026."""

from __future__ import annotations

import datetime
import socket
import sys
import threading

from flask import Flask, g, jsonify, redirect, request, session

from money99 import __version__
from money99.data_path import _resource_base, backups_dir, db_path, secret_key


def _resource_folder(name: str) -> str:
    return str(_resource_base() / "web" / name)


# Rotas acessíveis sem sessão autenticada.
_PUBLIC_PREFIXES = ("/static", "/api/auth")


def create_app(database_path: str | None = None) -> Flask:
    app = Flask(
        "money99",
        static_folder=_resource_folder("static"),
        template_folder=_resource_folder("templates"),
    )
    app.config["DB_PATH"] = database_path or str(db_path())
    app.config["SECRET_KEY"] = secret_key()

    from money99.db.repository import Repository
    from money99.db.session import connect, make_session, prepare_database

    engine = connect(app.config["DB_PATH"])
    app.config["MIGRATION_BACKUP"] = prepare_database(engine, backup_dir=backups_dir())
    app.config["ENGINE"] = engine

    def get_repo(profile_id: int | None = "__current__"):
        if "session" not in g:
            g.session = make_session(engine)
        if profile_id == "__current__":
            profile_id = session.get("profile_id")
        return Repository(g.session, profile_id)

    @app.teardown_appcontext
    def _close_session(exception=None):
        session = g.pop("session", None)
        if session is not None:
            if exception is None:
                session.commit()
            else:
                session.rollback()
            session.close()

    app.extensions["get_repo"] = get_repo

    from money99.api import register_blueprints

    register_blueprints(app)

    @app.before_request
    def _require_login():
        path = request.path
        if path == "/login" or path.startswith(_PUBLIC_PREFIXES):
            return None
        if session.get("user") is not None:
            return None
        if path.startswith("/api/"):
            return jsonify({"error": "não autenticado"}), 401
        return redirect("/login")

    @app.get("/login")
    def login_page():
        from flask import render_template

        if session.get("user") is not None:
            return redirect("/")
        return render_template("login.html", version=__version__)

    @app.get("/")
    def index():
        from flask import render_template

        return render_template("base.html")

    @app.get("/reports/print")
    def report_print():
        """Relatório consolidado em HTML pronto para impressão/PDF.

        pywebview ignora downloads via blob; oferecemos uma página dedicada que
        o usuário salva como PDF pelo diálogo de impressão do navegador.
        """
        from flask import render_template, request

        from money99.domain.money import format_brl
        from money99.services.reports import cash_flow, net_worth, spending_by_category

        repo = app.extensions["get_repo"]()
        year = request.args.get("year") or ""
        start = f"{year}-01-01" if year else "0000-01-01"
        end = f"{year}-12-31" if year else "9999-12-31"
        return render_template(
            "report_print.html",
            year=year,
            spending=spending_by_category(repo, start, end),
            worth=net_worth(repo),
            flow=cash_flow(repo, start, end),
            fmt=lambda cents: format_brl(cents, with_symbol=True),
            generated_at=datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        )

    @app.get("/reports/mei")
    def mei_print():
        """Relatório MEI (mensal/anual) em HTML pronto para impressão/PDF."""
        from flask import render_template, request

        from money99.domain.money import format_brl
        from money99.services.mei import monthly_caderno, monthly_report

        repo = app.extensions["get_repo"]()
        year = request.args.get("year") or str(datetime.date.today().year)
        if not year.isdigit():
            year = str(datetime.date.today().year)
        year = int(year)
        month_arg = request.args.get("month") or ""
        month = int(month_arg) if month_arg.isdigit() and 1 <= int(month_arg) <= 12 else None
        data = monthly_report(repo, year) if repo.profile_id else None
        caderno = (
            monthly_caderno(repo, year, month)
            if data is not None and month is not None
            else None
        )
        profile = repo.get_profile(repo.profile_id) if repo.profile_id else None
        return render_template(
            "mei_print.html",
            year=year,
            month=month,
            data=data,
            caderno=caderno,
            profile=profile,
            fmt=lambda cents: format_brl(cents, with_symbol=True),
            generated_at=datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        )

    return app


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run_webview() -> None:
    import webview

    app = create_app()
    port = _free_port()
    url = f"http://127.0.0.1:{port}/"
    thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, threaded=False),
        daemon=True,
    )
    thread.start()

    deadline = 50
    while deadline > 0:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            import time

            time.sleep(0.1)
            deadline -= 1

    webview.create_window("Money 2026", url)
    icon = _resource_base() / "web" / "static" / "img" / "icon.ico"
    webview.start(debug=not getattr(sys, "frozen", False), icon=str(icon))
