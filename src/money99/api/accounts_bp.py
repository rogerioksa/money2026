"""Blueprint de contas."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo
from money99.domain.account import Account, AccountType

bp = Blueprint("accounts", __name__, url_prefix="/api/accounts")


def _serialize(repo, account: Account) -> dict:
    balances = repo.account_balances(account.id)
    return {
        "id": account.id,
        "name": account.name,
        "type": account.type.value,
        "initial_balance": account.initial_balance,
        "active": account.active,
        "credit_limit": account.credit_limit,
        "balance": balances["balance"],
        "future": balances["future"],
    }


@bp.get("")
def list_accounts():
    repo = get_repo()
    active_only = request.args.get("active") == "1"
    return jsonify([_serialize(repo, a) for a in repo.list_accounts(active_only=active_only)])


@bp.post("")
def create_account():
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        account = Account(
            name=payload.get("name", ""),
            type=payload.get("type", "bank"),
            initial_balance=int(payload.get("initial_balance", 0)),
            active=bool(payload.get("active", True)),
            credit_limit=int(payload.get("credit_limit", 0)),
        )
        created = repo.add_account(account)
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(_serialize(repo, created)), 201


@bp.get("/<int:account_id>")
def get_account(account_id: int):
    repo = get_repo()
    try:
        account = repo.get_account(account_id)
    except LookupError as exc:
        return error(str(exc), 404)
    return jsonify(_serialize(repo, account))


@bp.put("/<int:account_id>")
def update_account(account_id: int):
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        current = repo.get_account(account_id)
        account = Account(
            id=account_id,
            name=payload.get("name", ""),
            type=payload.get("type", "bank"),
            initial_balance=int(payload.get("initial_balance", current.initial_balance)),
            active=bool(payload.get("active", True)),
            credit_limit=int(payload.get("credit_limit", 0)),
        )
        updated = repo.update_account(account)
    except LookupError as exc:
        return error(str(exc), 404)
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(_serialize(repo, updated))


@bp.delete("/<int:account_id>")
def delete_account(account_id: int):
    repo = get_repo()
    try:
        repo.delete_account(account_id)
    except LookupError as exc:
        return error(str(exc), 404)
    except ValueError as exc:
        return error(str(exc))
    return jsonify({"ok": True})


@bp.get("/<int:account_id>/balance")
def account_balance(account_id: int):
    repo = get_repo()
    as_of = request.args.get("as_of") or None
    try:
        balances = repo.account_balances(account_id, as_of=as_of)
    except LookupError as exc:
        return error(str(exc), 404)
    return jsonify(balances)


@bp.get("/<int:account_id>/reconciliation")
def reconciliation(account_id: int):
    from money99.services.reconcile import reconciliation_summary

    repo = get_repo()
    try:
        repo.get_account(account_id)
    except LookupError as exc:
        return error(str(exc), 404)
    return jsonify(reconciliation_summary(repo, account_id))


def _account_type_ok(value: str) -> bool:
    return value in {t.value for t in AccountType}
