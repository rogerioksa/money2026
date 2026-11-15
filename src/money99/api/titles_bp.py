"""Blueprint de títulos a pagar/receber (CAR/CAP)."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo
from money99.domain.title import Title
from money99.domain.transaction import Transaction

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
        "cost_center_id": title.cost_center_id,
        "favorecido": title.favorecido,
        "favorecido_id": title.favorecido_id,
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


@bp.get("/descriptions")
def list_title_descriptions():
    repo = get_repo()
    return jsonify(repo.list_title_descriptions(
        query=request.args.get("q", ""),
        limit=request.args.get("limit", 0, type=int),
    ))


@bp.get("/suggest-link")
def suggest_title_link():
    description = request.args.get("description", "")
    repo = get_repo()
    return jsonify(repo.suggest_title_link(description))


@bp.post("")
def create_title():
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    favorecido_id = payload.get("favorecido_id")
    favorecido_name = str(payload.get("favorecido", "") or "")
    if favorecido_id is not None:
        try:
            favorecido_id = int(favorecido_id)
            fav = repo.get_favorecido(favorecido_id)
            favorecido_name = fav.name
        except (TypeError, ValueError, LookupError) as exc:
            return error(str(exc), 404 if isinstance(exc, LookupError) else 400)
    try:
        title = Title(
            type=str(payload.get("type", "payable")),
            description=str(payload.get("description", "")),
            amount=int(payload.get("amount", 0)),
            due_date=str(payload.get("due_date", "")),
            account_id=payload.get("account_id"),
            category_id=payload.get("category_id"),
            cost_center_id=payload.get("cost_center_id"),
            favorecido=favorecido_name,
            favorecido_id=favorecido_id,
            notes=str(payload.get("notes", "") or ""),
        )
        if title.account_id is not None:
            title.account_id = int(title.account_id)
        if title.category_id is not None:
            title.category_id = int(title.category_id)
        if title.cost_center_id is not None:
            title.cost_center_id = int(title.cost_center_id)
    except (TypeError, ValueError) as exc:
        return error(str(exc))
    try:
        if title.account_id is not None:
            repo.get_account(title.account_id)
        if title.category_id is not None:
            repo.get_category(title.category_id)
        if title.cost_center_id is not None:
            repo.get_cost_center(title.cost_center_id)
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
    favorecido_id = payload.get("favorecido_id", existing.favorecido_id)
    favorecido_name = str(payload.get("favorecido", existing.favorecido) or "")
    if favorecido_id is not None and favorecido_id != existing.favorecido_id:
        favorecido_id = int(favorecido_id)
        try:
            fav = repo.get_favorecido(favorecido_id)
            favorecido_name = fav.name
        except LookupError as exc:
            return error(str(exc), 404)
    elif favorecido_id is None:
        favorecido_name = str(payload.get("favorecido", existing.favorecido) or "")
    title = Title(
        id=title_id,
        type=str(payload.get("type", existing.type)),
        description=str(payload.get("description", existing.description)),
        amount=int(payload.get("amount", existing.amount)),
        due_date=str(payload.get("due_date", existing.due_date)),
        status=str(payload.get("status", existing.status)),
        account_id=payload.get("account_id", existing.account_id),
        category_id=payload.get("category_id", existing.category_id),
        cost_center_id=payload.get("cost_center_id", existing.cost_center_id),
        favorecido=favorecido_name,
        favorecido_id=favorecido_id,
        notes=str(payload.get("notes", existing.notes) or ""),
        paid_date=str(payload.get("paid_date", existing.paid_date) or ""),
        paid_amount=int(payload.get("paid_amount", existing.paid_amount) or 0),
    )
    if title.account_id is not None:
        title.account_id = int(title.account_id)
    if title.category_id is not None:
        title.category_id = int(title.category_id)
    if title.cost_center_id is not None:
        title.cost_center_id = int(title.cost_center_id)
    try:
        if title.account_id is not None:
            repo.get_account(title.account_id)
        if title.category_id is not None:
            repo.get_category(title.category_id)
        if title.cost_center_id is not None:
            repo.get_cost_center(title.cost_center_id)
    except LookupError as exc:
        return error(str(exc), 404)
    try:
        updated = repo.update_title(title)
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(_serialize(updated))


@bp.post("/<int:title_id>/pay")
def pay_title(title_id: int):
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        title = repo.get_title(title_id)
    except LookupError as exc:
        return error(str(exc), 404)
    if title.status == "paid":
        return jsonify(_serialize(title))
    paid_date = str(payload.get("paid_date") or date.today().isoformat())
    pay_amount = payload.get("amount", title.amount - title.paid_amount)
    try:
        pay_amount = int(pay_amount)
    except (TypeError, ValueError):
        return error("valor pago inválido")
    if pay_amount <= 0:
        return error("valor pago deve ser positivo")
    remaining = title.amount - title.paid_amount
    if pay_amount > remaining:
        pay_amount = remaining
    account_id = payload.get("account_id", title.account_id)
    if account_id is not None:
        account_id = int(account_id)
        try:
            repo.get_account(account_id)
        except LookupError as exc:
            return error(str(exc), 404)
    try:
        if account_id is not None:
            amount = pay_amount if title.type == "receivable" else -pay_amount
            repo.add_transaction(Transaction(
                date=paid_date,
                description=f"{title.description} (título)",
                account_id=account_id,
                amount=amount,
                category_id=title.category_id,
                cost_center_id=title.cost_center_id,
            ))
    except (ValueError, TypeError, LookupError) as exc:
        return error(str(exc))
    title.paid_amount = title.paid_amount + pay_amount
    title.paid_date = paid_date
    if title.paid_amount >= title.amount:
        title.status = "paid"
        title.paid_amount = title.amount
    else:
        title.status = "partial"
    title.account_id = account_id if account_id is not None else title.account_id
    try:
        updated = repo.update_title(title)
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(_serialize(updated))


@bp.get("/alerts")
def title_alerts():
    repo = get_repo()
    today = date.today().isoformat()
    overdue = []
    upcoming = []
    for title in repo.list_titles(status="open"):
        if title.due_date < today:
            overdue.append(_serialize(title))
        elif title.due_date <= _add_days(today, 7):
            upcoming.append(_serialize(title))
    return jsonify({"overdue": overdue, "upcoming": upcoming})


def _add_days(iso: str, days: int) -> str:
    from datetime import date, timedelta

    y, m, d = (int(x) for x in iso.split("-"))
    return (date(y, m, d) + timedelta(days=days)).isoformat()


@bp.delete("/<int:title_id>")
def delete_title(title_id: int):
    repo = get_repo()
    try:
        repo.delete_title(title_id)
    except LookupError as exc:
        return error(str(exc), 404)
    return jsonify({"ok": True})