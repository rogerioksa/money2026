"""Blueprint de transações."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo
from money99.domain.transaction import Split, Transaction

bp = Blueprint("transactions", __name__, url_prefix="/api/transactions")


def _serialize(txn: Transaction) -> dict:
    return {
        "id": txn.id,
        "date": txn.date,
        "description": txn.description,
        "account_id": txn.account_id,
        "amount": txn.amount,
        "category_id": txn.category_id,
        "transfer_account_id": txn.transfer_account_id,
        "splits": [
        {"category_id": s.category_id, "amount": s.amount, "cost_center_id": s.cost_center_id}
        for s in txn.splits
    ],
    "cost_center_id": txn.cost_center_id,
        "notes": txn.notes,
        "reconciled": txn.reconciled,
        "doc_issued": txn.doc_issued,
    }


def _parse_payload(payload: dict) -> Transaction:
    return Transaction(
        date=str(payload.get("date", "")),
        description=str(payload.get("description", "")),
        account_id=int(payload.get("account_id", 0)),
        amount=int(payload.get("amount", 0)),
        category_id=payload.get("category_id"),
        transfer_account_id=payload.get("transfer_account_id"),
        cost_center_id=payload.get("cost_center_id"),
        splits=[
            Split(
                category_id=int(s.get("category_id", 0)),
                amount=int(s.get("amount", 0)),
                cost_center_id=s.get("cost_center_id"),
            )
            for s in payload.get("splits", [])
        ],
        notes=str(payload.get("notes", "")),
        reconciled=bool(payload.get("reconciled", False)),
        doc_issued=bool(payload.get("doc_issued", False)),
    )


@bp.get("/descriptions")
def list_descriptions():
    repo = get_repo()
    return jsonify(repo.list_descriptions(
        query=request.args.get("q", ""),
        limit=request.args.get("limit", 20, type=int),
    ))


@bp.get("")
def list_transactions():
    repo = get_repo()
    try:
        txns = repo.list_transactions(
            account_id=request.args.get("account_id", type=int),
            category_id=request.args.get("category_id", type=int),
            start=request.args.get("start"),
            end=request.args.get("end"),
            reconciled=(
                None
                if "reconciled" not in request.args
                else request.args["reconciled"] == "1"
            ),
        )
    except ValueError as exc:
        return error(str(exc))
    return jsonify([_serialize(t) for t in txns])


@bp.post("")
def create_transaction():
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        txn = repo.add_transaction(_parse_payload(payload))
    except LookupError as exc:  # conta/categoria referenciada não existe
        return error(str(exc))
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(_serialize(txn)), 201


@bp.put("/<int:txn_id>")
def update_transaction(txn_id: int):
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        repo.get_transaction(txn_id)
    except LookupError as exc:
        return error(str(exc), 404)
    try:
        txn = _parse_payload(payload)
        txn.id = txn_id
        updated = repo.update_transaction(txn)
    except LookupError as exc:  # conta/categoria referenciada não existe
        return error(str(exc))
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(_serialize(updated))


@bp.get("/suggest-link")
def suggest_link():
    description = request.args.get("description", "")
    repo = get_repo()
    return jsonify(repo.suggest_link(description))


@bp.delete("/<int:txn_id>")
def delete_transaction(txn_id: int):
    repo = get_repo()
    try:
        repo.delete_transaction(txn_id)
    except LookupError as exc:
        return error(str(exc), 404)
    return jsonify({"ok": True})


@bp.post("/<int:txn_id>/reconcile")
def reconcile_transaction(txn_id: int):
    payload = request.get_json(silent=True) or {}
    repo = get_repo()
    try:
        repo.set_reconciled(txn_id, bool(payload.get("reconciled", True)))
    except LookupError as exc:
        return error(str(exc), 404)
    return jsonify({"ok": True})
