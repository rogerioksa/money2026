from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from gnc_lite.services import auth as auth_service

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login() -> tuple:
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"error": "no_company_open"}), 400
    auth = auth_service.AuthService(web.ledger.repo)
    user = auth.authenticate(username, password)
    if user is None:
        return jsonify({"error": "Usuario ou senha invalidos"}), 401
    current_app.config["USER_ID"] = user.id
    web.user = user
    return jsonify(
        {
            "ok": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "display": getattr(user, "display_name", None)
                or getattr(user, "display", None)
                or user.username,
                "role": user.role.value,
                "can_write": user.role.can_write,
                "is_admin": user.role.is_admin,
            },
        }
    )


@bp.get("/me")
def me() -> tuple:
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"user": None})
    user = getattr(web, "user", None)
    if user is None:
        return jsonify({"user": None})
    return jsonify(
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "display": getattr(user, "display_name", None) or user.username,
                "role": user.role.value,
                "can_write": user.role.can_write,
                "is_admin": user.role.is_admin,
            }
        }
    )


@bp.post("/logout")
def logout() -> tuple:
    web = getattr(g, "web", None)
    if web is not None:
        web.user = None
    current_app.config["USER_ID"] = None
    return jsonify({"ok": True})
