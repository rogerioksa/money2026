"""Blueprint de títulos a pagar/receber (CAR/CAP)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo
from money99.domain.title import Title

bp = Blueprint("titles", __name__, url_prefix="/api/titles")


def _serialize(title):
    return {
        "id": title.id,
        "type": title.type,
        "description": title.description,
        "amount": title.amount,
        "due_date": title.due_date,
        "status": title.status,
        "account_id": title.account_id,
        "category_id": title.category_id,
        "favorecido": title.favorecido,
        "notes": title.notes,
        "paid_date": title.paid_date,
        "paid_amount": title.paid_amount,
    }


@bp.get("")
def list_titles():
    repo = get_repo()
    type_filter = request.args.get("type")
    status_filter = request.args.get("status")
    titles = repo.list_titles(type=type_filter, status=status_filter)
    return jsonify([_serialize(t) for t in titles])


@bp.post("")
def create_title():
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        title = Title(
            type=str(payload.get("type", "payable")),
            description=str(payload.get("description", "")),
            amount=int(payload.get("amount", 0)),
            due_date=str(payload.get("due_date", "")),
            account_id=payload.get("account_id"),
            category_id=payload.get("category_id"),
            favorecido=str(payload.get("favorecido", "") or ""),
            notes=str(payload.get("notes", "") or ""),
        )
        if title.account_id is not None:
            title.account_id = int(title.account_id)
        if title.category_id is not None:
            title.category_id = int(title.category_id)
    except (TypeError, ValueError) as exc:
        return error(str(exc))
    try:
        if title.account_id is not None:
            repo.get_account(title.account_id)
        if title.category_id is not None:
            repo.get_category(title.category_id)
    except LookupError as exc:
        return error(str(exc), 404)
    created = repo.add_title(title)
    return jsonify(_serialize(created)), 201


@bp.put("/<int:title_id>")
def update_title(title_id: int):
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        existing = repo.get_title(title_id)
    except LookupError as exc:
        return error(str(exc), 404)
    title = Title(
        id=title_id,
        type=str(payload.get("type", existing.type)),
        description=str(payload.get("description", existing.description)),
        amount=int(payload.get("amount", existing.amount)),
        due_date=str(payload.get("due_date", existing.due_date)),
        status=str(payload.get("status", existing.status)),
        account_id=payload.get("account_id", existing.account_id),
        category_id=payload.get("category_id", existing.category_id),
        favorecido=str(payload.get("favorecido", existing.favorecido) or ""),
        notes=str(payload.get("notes", existing.notes) or ""),
        paid_date=str(payload.get("paid_date", existing.paid_date) or ""),
        paid_amount=int(payload.get("paid_amount", existing.paid_amount) or 0),
    )
    if title.account_id is not None:
        title.account_id = int(title.account_id)
    if title.category_id is not None:
        title.category_id = int(title.category_id)
    try:
        if title.account_id is not None:
            repo.get_account(title.account_id)
        if title.category_id is not None:
            repo.get_category(title.category_id)
    except LookupError as exc:
        return error(str(exc), 404)
    try:
        updated = repo.update_title(title)
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(_serialize(updated))


@bp.delete("/<int:title_id>")
def delete_title(title_id: int):
    repo = get_repo()
    try:
        repo.delete_title(title_id)
    except LookupError as exc:
        return error(str(exc), 404)
    return jsonify({"ok": True})