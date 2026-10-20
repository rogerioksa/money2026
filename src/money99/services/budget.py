"""Orçamento: planejado x realizado por categoria/mês."""

from __future__ import annotations

from money99.db.repository import Repository


def _month_range(year: int, month: int) -> tuple[str, str]:
    """Limites inclusivos (strings ISO) do mês. Fim no último dia possível."""
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-31"


def actual_by_category(repo: Repository, year: int, month: int) -> dict[int, int]:
    """Soma (valor absoluto) gasto por categoria no mês."""
    start, end = _month_range(year, month)
    totals: dict[int, int] = {}
    for txn in repo.list_transactions(start=start, end=end):
        if txn.transfer_account_id is not None:
            continue
        if txn.splits:
            for split in txn.splits:
                totals[split.category_id] = totals.get(split.category_id, 0) + abs(split.amount)
        elif txn.category_id is not None:
            totals[txn.category_id] = totals.get(txn.category_id, 0) + abs(txn.amount)
    return totals


def budget_report(repo: Repository, year: int, month: int) -> list[dict]:
    """Lista categorias de despesa com planejado, realizado e saldo."""
    planned = {row.category_id: row.planned for row in repo.list_budget(year, month)}
    actual = actual_by_category(repo, year, month)
    result = []
    for cat in repo.list_categories(kind="expense"):
        p = planned.get(cat.id, 0)
        a = actual.get(cat.id, 0)
        if p == 0 and a == 0:
            continue
        result.append({
            "category_id": cat.id,
            "category": cat.name,
            "planned": p,
            "actual": a,
            "remaining": p - a,
        })
    return result
