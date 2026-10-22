"""Blueprint de autenticação: setup inicial, login, logout, senha e sessão."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from money99.api._common import error, get_repo
from money99.services.auth import hash_password, verify_password

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

SESSION_USER = "user"
SESSION_PROFILE = "profile_id"


def current_user() -> str | None:
    return session.get(SESSION_USER)


def current_profile_id() -> int | None:
    return session.get(SESSION_PROFILE)


def _default_profile_id(repo) -> int | None:
    profiles = repo.list_profiles()
    return profiles[0].id if profiles else None


def _status_payload(repo) -> dict:
    return {"has_user": repo.count_users() > 0, "authenticated": current_user() is not None}


@bp.get("/status")
def status():
    repo = get_repo()
    if session.get(SESSION_PROFILE) is None and current_user() is not None:
        session[SESSION_PROFILE] = _default_profile_id(repo)
    return jsonify({
        **_status_payload(repo),
        "username": current_user(),
        "profile_id": current_profile_id(),
    })


@bp.post("/setup")
def setup():
    """Cria o usuário local na primeira execução."""
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    repo = get_repo()
    if repo.count_users() > 0:
        return error("usuário já cadastrado; faça login")
    if not username:
        return error("usuário é obrigatório")
    if len(password) < 4:
        return error("senha deve ter ao menos 4 caracteres")
    password_hash, salt = hash_password(password)
    repo.add_user(username, password_hash, salt)
    session[SESSION_USER] = username
    session[SESSION_PROFILE] = _default_profile_id(repo)
    return jsonify({"ok": True, "username": username}), 201


@bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    repo = get_repo()
    user = repo.get_user(username)
    if user is None or not verify_password(password, user.password_hash, user.salt):
        return error("usuário ou senha inválidos", 401)
    session[SESSION_USER] = user.username
    session[SESSION_PROFILE] = _default_profile_id(repo)
    return jsonify({"ok": True, "username": user.username})


@bp.post("/logout")
def logout():
    session.pop(SESSION_USER, None)
    session.pop(SESSION_PROFILE, None)
    return jsonify({"ok": True})


@bp.post("/change-password")
def change_password():
    """Troca a senha do usuário atual (exige senha atual)."""
    payload = request.get_json(silent=True) or {}
    current = str(payload.get("current_password", ""))
    new = str(payload.get("new_password", ""))
    username = current_user()
    if username is None:
        return error("não autenticado", 401)
    if len(new) < 4:
        return error("nova senha deve ter ao menos 4 caracteres")
    repo = get_repo()
    user = repo.get_user(username)
    if user is None or not verify_password(current, user.password_hash, user.salt):
        return error("senha atual incorreta", 400)
    password_hash, salt = hash_password(new)
    user.password_hash = password_hash
    user.salt = salt
    return jsonify({"ok": True})


@bp.put("/profile")
def switch_profile():
    """Troca o perfil ativo da sessão."""
    payload = request.get_json(silent=True) or {}
    profile_id = payload.get("profile_id")
    repo = get_repo()
    try:
        profile = repo.get_profile(int(profile_id))
    except (LookupError, TypeError, ValueError):
        return error("perfil inválido", 404)
    session[SESSION_PROFILE] = profile.id
    return jsonify({"ok": True, "profile_id": profile.id, "name": profile.name})
