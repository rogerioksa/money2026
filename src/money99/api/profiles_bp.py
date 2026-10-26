"""Blueprint de perfis (pessoal / empresarial-MEI)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from money99.api._common import error, get_repo
from money99.domain.profile import DEFAULT_ANNUAL_LIMIT, Profile, ProfileKind

bp = Blueprint("profiles", __name__, url_prefix="/api/profiles")


def _serialize(profile: Profile) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "kind": profile.kind.value,
        "cnpj": profile.cnpj,
        "legal_name": profile.legal_name,
        "trade_name": profile.trade_name,
        "opened_on": profile.opened_on,
        "annual_limit": profile.annual_limit,
        "activity": (
        ",".join(getattr(a, "value", a) for a in profile.activity)
        if isinstance(profile.activity, (list, tuple))
        else getattr(profile.activity, "value", profile.activity)
    ),
    "activities": [
        getattr(a, "value", a) for a in (
            profile.activity if isinstance(profile.activity, (list, tuple)) else [profile.activity]
        )
    ],
        "active": profile.active,
    }


def _build(payload: dict, *, profile_id: int | None = None) -> Profile:
    kind = str(payload.get("kind", "personal") or "personal")
    annual_limit = (
        0 if kind == "personal" else int(payload.get("annual_limit", DEFAULT_ANNUAL_LIMIT))
    )
    activities_payload = payload.get("activities")
    if activities_payload is None:
        activity_value = payload.get("activity", "servicos") or "servicos"
        if isinstance(activity_value, str):
            activities = [x.strip() for x in activity_value.split(",") if x.strip()]
        else:
            activities = activity_value
    else:
        activities = activities_payload
    return Profile(
        id=profile_id,
        name=str(payload.get("name", "")),
        kind=kind,
        cnpj=str(payload.get("cnpj", "") or ""),
        legal_name=str(payload.get("legal_name", "") or ""),
        trade_name=str(payload.get("trade_name", "") or ""),
        opened_on=str(payload.get("opened_on", "") or ""),
        annual_limit=annual_limit,
        activity=activities or "servicos",
        active=bool(payload.get("active", True)),
    )


@bp.get("")
def list_profiles():
    repo = get_repo()
    return jsonify([_serialize(p) for p in repo.list_profiles()])


@bp.post("")
def create_profile():
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        created = repo.add_profile(_build(payload))
        if created.id is not None:
            repo.seed_default_categories(created.id)
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(_serialize(created)), 201


@bp.get("/<int:profile_id>")
def get_profile(profile_id: int):
    repo = get_repo()
    try:
        return jsonify(_serialize(repo.get_profile(profile_id)))
    except LookupError as exc:
        return error(str(exc), 404)


@bp.put("/<int:profile_id>")
def update_profile(profile_id: int):
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        updated = repo.update_profile(_build(payload, profile_id=profile_id))
    except LookupError as exc:
        return error(str(exc), 404)
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(_serialize(updated))


@bp.delete("/<int:profile_id>")
def delete_profile(profile_id: int):
    repo = get_repo()
    try:
        repo.delete_profile(profile_id)
    except LookupError as exc:
        return error(str(exc), 404)
    except ValueError as exc:
        return error(str(exc))
    if session.get("profile_id") == profile_id:
        profiles = repo.list_profiles()
        session["profile_id"] = profiles[0].id if profiles else None
    return jsonify({"ok": True})


def _kinds():
    return {k.value for k in ProfileKind}
