from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from gnc_lite.domain.user import Role, UserError
from gnc_lite.services.auth import AuthService

bp = Blueprint("users", __name__, url_prefix="/api/users")


def _json(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display": user.display_name or user.username,
        "role": user.role.value,
        "active": user.active,
        "can_write": user.role.can_write,
        "is_admin": user.role.is_admin,
    }


def _require_admin():
    web = getattr(g, "web", None)
    if web is None:
        return None, (jsonify({"error": "no_company_open"}), 400)
    user = getattr(web, "user", None)
    if user is None or not user.role.is_admin:
        return None, (jsonify({"error": "forbidden"}), 403)
    return AuthService(web.ledger.repo), None


@bp.get("")
def list_users() -> tuple:
    auth, err = _require_admin()
    if err is not None:
        return err
    return jsonify({"users": [_json(u) for u in auth.list_users()]})


@bp.post("")
def create_user() -> tuple:
    web = getattr(g, "web", None)
    auth, err = _require_admin()
    if err is not None:
        return err
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    try:
        role = Role(str(payload.get("role") or Role.VIEWER.value))
    except ValueError:
        return jsonify({"error": "Papel invalido."}), 400
    try:
        user = auth.create_user(
            username, password, role, str(payload.get("display") or "")
        )
        web.dbsession.commit()
    except UserError as exc:
        web.dbsession.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "user": _json(user)})


@bp.patch("/<int:user_id>")
def update_user(user_id: int) -> tuple:
    web = getattr(g, "web", None)
    auth, err = _require_admin()
    if err is not None:
        return err
    repo = web.ledger.repo
    user = repo.get_user(user_id)
    if user is None:
        return jsonify({"error": "Usuario nao encontrado."}), 404
    payload = request.get_json(silent=True) or {}
    try:
        if "role" in payload:
            user = auth.set_role(user, Role(str(payload["role"])))
        if "active" in payload:
            user = auth.set_active(user, bool(payload["active"]))
        if "password" in payload and payload["password"]:
            user = auth.set_password(user, str(payload["password"]))
        if "username" in payload or "display" in payload:
            user = auth.rename(
                user,
                str(payload.get("username", user.username)),
                str(payload.get("display", user.display_name)),
            )
        web.dbsession.commit()
    except (UserError, ValueError) as exc:
        web.dbsession.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "user": _json(user)})
