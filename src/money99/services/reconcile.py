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
