"""Orçamento: planejado (anual) x realizado por categoria/mês e por conta."""

from __future__ import annotations

from money99.db.repository import Repository


def _month_range(year: int, month: int) -> tuple[str, str]:
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-31"


def monthly_share(annual: int, month: int) -> int:
    """Divide um valor anual em 12 parcelas, distribuindo o resto nos primeiros meses."""
    if annual <= 0:
        return 0
    base = annual // 12
    remainder = annual % 12
    return base + (1 if month <= remainder else 0)


def actual_by_category(repo: Repository, year: int, month: int) -> dict[int, int]:
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


def annual_actual_by_category(repo: Repository, year: int) -> dict[int, int]:
    totals: dict[int, int] = {}
    for month in range(1, 13):
        for cat_id, value in actual_by_category(repo, year, month).items():
            totals[cat_id] = totals.get(cat_id, 0) + value
    return totals


def budget_report(repo: Repository, year: int, month: int) -> list[dict]:
    annual_planned = {row.category_id: row.annual_planned for row in repo.list_annual_budget(year)}
    actual = actual_by_category(repo, year, month)
    result = []
    for cat in repo.list_categories(kind="expense"):
        ap = annual_planned.get(cat.id, 0)
        p = monthly_share(ap, month)
        a = actual.get(cat.id, 0)
        if ap == 0 and a == 0:
            continue
        result.append({
            "category_id": cat.id,
            "category": cat.name,
            "planned": p,
            "actual": a,
            "remaining": p - a,
            "annual_planned": ap,
            "annual_remaining": ap - annual_actual_by_category(repo, year).get(cat.id, 0),
        })
    return result


def annual_budget_report(repo: Repository, year: int) -> list[dict]:
    annual_planned = {row.category_id: row.annual_planned for row in repo.list_annual_budget(year)}
    actual = annual_actual_by_category(repo, year)
    result = []
    for cat in repo.list_categories(kind="expense"):
        ap = annual_planned.get(cat.id, 0)
        a = actual.get(cat.id, 0)
        if ap == 0 and a == 0:
            continue
        result.append({
            "category_id": cat.id,
            "category": cat.name,
            "annual_planned": ap,
            "annual_actual": a,
            "annual_remaining": ap - a,
        })
    return result


def actual_by_account(repo: Repository, year: int, month: int | None = None) -> list[dict]:
    months = [month] if month else list(range(1, 13))
    totals: dict[int, int] = {}
    for m in months:
        start, end = _month_range(year, m)
        for txn in repo.list_transactions(start=start, end=end):
            if txn.transfer_account_id is not None:
                continue
            amount = 0
            if txn.splits:
                amount = sum(abs(s.amount) for s in txn.splits)
            elif txn.category_id is not None:
                amount = abs(txn.amount)
            else:
                amount = abs(txn.amount)
            totals[txn.account_id] = totals.get(txn.account_id, 0) + amount
    result = []
    for acc in repo.list_accounts():
        result.append({
            "account_id": acc.id,
            "account": acc.name,
            "actual": totals.get(acc.id, 0),
        })
    return result


def budget_alerts(repo: Repository, year: int, month: int) -> dict:
    monthly = []
    for row in budget_report(repo, year, month):
        if row["planned"] > 0 and row["actual"] > row["planned"]:
            monthly.append({
                "category_id": row["category_id"],
                "category": row["category"],
                "planned": row["planned"],
                "actual": row["actual"],
                "over": row["actual"] - row["planned"],
            })
    annual = []
    for row in annual_budget_report(repo, year):
        if row["annual_planned"] > 0 and row["annual_actual"] > row["annual_planned"]:
            annual.append({
                "category_id": row["category_id"],
                "category": row["category"],
                "annual_planned": row["annual_planned"],
                "annual_actual": row["annual_actual"],
                "over": row["annual_actual"] - row["annual_planned"],
            })
    return {"monthly": monthly, "annual": annual}