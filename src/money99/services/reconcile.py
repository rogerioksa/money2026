"""Conciliação: resumo por conta (conciliado x pendente x saldo do extrato)."""

from __future__ import annotations

from money99.db.repository import Repository


def reconciliation_summary(repo: Repository, account_id: int) -> dict:
    """Resumo de conciliação: saldo atual, conciliado, pendentes, diferença."""
    balance = repo.account_balance(account_id)
    reconciled_total = 0
    pending_count = 0
    pending_total = 0
    for txn in repo.list_transactions(account_id=account_id):
        signed = txn.amount if txn.account_id == account_id else -txn.amount
        if txn.reconciled:
            reconciled_total += signed
        else:
            pending_count += 1
            pending_total += signed
    return {
        "account_id": account_id,
        "balance": balance,
        "reconciled_total": reconciled_total,
        "pending_count": pending_count,
        "pending_total": pending_total,
        "difference": balance - reconciled_total,
    }


def suggest_matches(repo, account_id: int, *, day_window: int = 3) -> list[dict]:
    """Sugere pares de lançamentos não conciliados com mesmo valor (absoluto)
    e datas próximas, para revisão em lote na conciliação."""
    from datetime import date

    txns = [
        t for t in repo.list_transactions(account_id=account_id)
        if not t.reconciled
    ]
    # normaliza para a perspectiva da conta
    items = []
    for t in txns:
        signed = t.amount if t.account_id == account_id else -t.amount
        items.append({"txn": t, "signed": signed, "abs": abs(signed)})

    groups: list[dict] = []
    used: set[int] = set()
    # ordena por data para agrupar
    items.sort(key=lambda x: x["txn"].date)
    for i, a in enumerate(items):
        if a["txn"].id in used:
            continue
        candidates = []
        for b in items[i + 1 :]:
            if b["txn"].id in used:
                continue
            if a["abs"] != b["abs"] or a["abs"] == 0:
                continue
            try:
                da = date.fromisoformat(a["txn"].date)
                db = date.fromisoformat(b["txn"].date)
            except ValueError:
                continue
            if abs((da - db).days) <= day_window:
                candidates.append(b)
        if candidates:
            used.add(a["txn"].id)
            for c in candidates:
                used.add(c["txn"].id)
            groups.append({
                "amount": a["abs"],
                "transactions": [
                    {
                        "id": a["txn"].id,
                        "date": a["txn"].date,
                        "description": a["txn"].description,
                        "amount": a["signed"],
                    }
                ] + [
                    {
                        "id": c["txn"].id,
                        "date": c["txn"].date,
                        "description": c["txn"].description,
                        "amount": c["signed"],
                    }
                    for c in candidates
                ],
            })
    return groups
