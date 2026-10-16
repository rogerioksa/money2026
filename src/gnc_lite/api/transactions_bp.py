from datetime import date

from flask import Blueprint, g, jsonify, request

from gnc_lite.domain.money import Money
from gnc_lite.domain.transaction import Split, Transaction
from gnc_lite.services import importer

bp = Blueprint("transactions", __name__, url_prefix="/api/transactions")


def _split_json(split) -> dict:
    return {
        "account_id": split.account.id,
        "account_code": split.account.code,
        "account_name": split.account.name,
        "minor_units": split.amount.minor_units,
    }


def _tx_json(ledger, t) -> dict:
    return {
        "id": t.id,
        "date": t.date.isoformat(),
        "description": t.description or "",
        "payee": t.payee or "",
        "splits": [_split_json(s) for s in t.splits],
    }


@bp.get("")
def list_transactions() -> tuple:
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"transactions": []})
    ledger = web.ledger
    txs = ledger.transactions()
    out = [_tx_json(ledger, t) for t in txs[-200:]]  # keep recent window
    out.reverse()
    return jsonify({"transactions": out})


@bp.post("")
def post_transaction() -> tuple:
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    try:
        tx_date = date.fromisoformat(str(payload.get("date")))
    except Exception:
        return jsonify({"error": "invalid_date"}), 400
    description = str(payload.get("description") or "")
    payee = str(payload.get("payee") or "")
    splits = payload.get("splits") or []
    if not splits:
        return jsonify({"error": "no_splits"}), 400
    sp = []
    ledger = web.ledger
    for s in splits:
        acc = ledger.repo.get_account(int(s["account_id"]))
        if acc is None:
            return jsonify({"error": f"bad_account:{s['account_id']}"}), 400
        amt = Money(int(s["minor_units"]), acc.currency)
        sp.append(Split(acc, amt))
    try:
        tx = Transaction(date=tx_date, description=description, payee=payee, splits=sp)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    ledger.post(tx)
    web.dbsession.commit()
    return jsonify({"ok": True, "transaction_id": tx.id})


@bp.post("/many")
def post_many() -> tuple:
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    items = payload.get("transactions") or []
    ledger = web.ledger
    new = []
    for payload_tx in items[:200]:
        try:
            tx_date = date.fromisoformat(str(payload_tx.get("date")))
        except Exception:
            continue
        description = str(payload_tx.get("description") or "")
        payee = str(payload_tx.get("payee") or "")
        splits = payload_tx.get("splits") or []
        if len(splits) != 2:
            continue
        sp = []
        ok = True
        for s in splits:
            acc = ledger.repo.get_account(int(s["account_id"]))
            if acc is None:
                ok = False
                break
            sp.append(Split(acc, Money(int(s["minor_units"]), acc.currency)))
        if not ok:
            continue
        new.append(Transaction(date=tx_date, description=description, payee=payee, splits=sp))
    if new:
        new, skipped = importer.partition_new(ledger, new)
        if new:
            ledger.post_many(new)
            web.dbsession.commit()
            return jsonify({"ok": True, "posted": len(new), "skipped": skipped})
    return jsonify({"ok": True, "posted": 0, "skipped": len(items)})


@bp.get("/running-balance")
def running_balance() -> tuple:
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"rows": []})
    account_id = request.args.get("account_id", type=int)
    if account_id is None:
        return jsonify({"rows": []})
    ledger = web.ledger
    acc = ledger.repo.get_account(account_id)
    if acc is None:
        return jsonify({"rows": []})
    txs = ledger.transactions()  # ordem cronologica (data, id)
    running = 0
    rows = []
    for t in txs:
        for s in t.splits:
            if s.account.id == account_id:
                running += s.amount.minor_units
                others = [o for o in t.splits if o.account.id != account_id]
                transfer = (
                    f"{others[0].account.code} {others[0].account.name}"
                    if len(others) == 1
                    else (f"{len(others)} contas" if others else "")
                )
                rows.append(
                    {
                        "id": t.id,
                        "date": t.date.isoformat(),
                        "description": t.description or "",
                        "payee": t.payee or "",
                        "transfer": transfer,
                        "debit": s.amount.minor_units if s.amount.minor_units > 0 else 0,
                        "credit": -s.amount.minor_units if s.amount.minor_units < 0 else 0,
                        "balance": running,
                    }
                )
    return jsonify({"rows": rows})
