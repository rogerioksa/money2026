"""Blueprint de importação de extratos (QIF/OFX) e exportação."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from money99.api._common import error, get_repo
from money99.db.repository import Repository
from money99.domain.transaction import Transaction
from money99.services.importer import StatementParseError, parse_statement

bp = Blueprint("imports", __name__, url_prefix="/api/import")


def _serialize(txn) -> dict:
    return {
        "date": txn.date,
        "amount": txn.amount,
        "description": txn.description,
        "external_id": txn.external_id,
        "raw_category": txn.raw_category,
    }


def _existing_keys(repo: Repository, account_id: int) -> set[tuple[str, int, str]]:
    keys = set()
    for txn in repo.list_transactions(account_id=account_id):
        keys.add((txn.date, txn.amount, txn.description))
    return keys


@bp.post("/preview")
def preview():
    payload = request.get_json(silent=True) or {}
    content = payload.get("content", "")
    filename = payload.get("filename", "")
    if not content.strip():
        return error("conteúdo vazio")
    try:
        parsed = parse_statement(content, filename)
    except StatementParseError as exc:
        return error(str(exc))

    account_id = payload.get("account_id")
    skipped = 0
    transactions = parsed
    if account_id is not None:
        repo = get_repo()
        try:
            repo.get_account(int(account_id))
        except (LookupError, TypeError, ValueError):
            return error("conta inválida", 404)
        existing = _existing_keys(repo, int(account_id))
        filtered = []
        for txn in parsed:
            key = (txn.date, txn.amount, txn.description)
            if key in existing:
                skipped += 1
                continue
            filtered.append(txn)
        transactions = filtered
    return jsonify({
        "count": len(transactions),
        "skipped": skipped,
        "transactions": [_serialize(t) for t in transactions],
    })


@bp.post("/commit")
def commit():
    """Importa transações sem categoria (a categorização é feita no extrato)."""
    payload = request.get_json(silent=True) or {}
    account_id = payload.get("account_id")
    transactions = payload.get("transactions", [])
    if account_id is None:
        return error("account_id é obrigatório")
    if not transactions:
        return error("nenhuma transação para importar")

    repo = get_repo()
    try:
        repo.get_account(int(account_id))
    except LookupError as exc:
        return error(str(exc), 404)

    existing = _existing_keys(repo, int(account_id))
    imported, skipped = 0, 0
    try:
        for item in transactions:
            key = (item.get("date"), int(item.get("amount", 0)), item.get("description", ""))
            if key in existing:
                skipped += 1
                continue
            description = str(item.get("description", ""))
            link = repo.suggest_link(description)
            repo.add_transaction(Transaction(
                date=str(item.get("date", "")),
                description=description,
                account_id=int(account_id),
                amount=int(item.get("amount", 0)),
                category_id=item.get("category_id", link.get("category_id")),
                cost_center_id=item.get("cost_center_id", link.get("cost_center_id")),
            ))
            existing.add(key)
            imported += 1
    except (ValueError, TypeError, LookupError) as exc:
        return error(str(exc))
    return jsonify({"imported": imported, "skipped": skipped})
