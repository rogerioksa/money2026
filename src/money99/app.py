"""Flask + launcher pywebview do Money 99."""

from __future__ import annotations

import socket
import sys
import threading

from flask import Flask, g

from money99.data_path import _resource_base, db_path


def _resource_folder(name: str) -> str:
    return str(_resource_base() / "web" / name)


def create_app(database_path: str | None = None) -> Flask:
    app = Flask(
        "money99",
        static_folder=_resource_folder("static"),
        template_folder=_resource_folder("templates"),
    )
    app.config["DB_PATH"] = database_path or str(db_path())

    from money99.db.repository import Repository
    from money99.db.session import connect, init_db, make_session

    engine = connect(app.config["DB_PATH"])
    init_db(engine)
    app.config["ENGINE"] = engine

    def get_repo() -> Repository:
        if "session" not in g:
            g.session = make_session(engine)
        return Repository(g.session)

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

    @app.get("/")
    def index():
        from flask import render_template

        return render_template("base.html")

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

    webview.create_window("Money 99", url)
    webview.start(debug=not getattr(sys, "frozen", False))
