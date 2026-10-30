"""Relatórios: gastos por categoria, patrimônio líquido, fluxo de caixa."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from money99.db.repository import Repository


def spending_by_category(
    repo: Repository, start: str, end: str, kind: str = "expense"
) -> list[dict]:
    """Total por categoria no período (valores absolutos)."""
    totals: dict[int, int] = {}
    for txn in repo.list_transactions(start=start, end=end):
        if txn.transfer_account_id is not None:
            continue
        if txn.splits:
            for split in txn.splits:
                totals[split.category_id] = totals.get(split.category_id, 0) + abs(split.amount)
        elif txn.category_id is not None:
            totals[txn.category_id] = totals.get(txn.category_id, 0) + abs(txn.amount)

    result = []
    for cat in repo.list_categories(kind=kind):
        total = totals.get(cat.id, 0)
        if total:
            result.append({"category_id": cat.id, "category": cat.name, "total": total})
    result.sort(key=lambda r: r["total"], reverse=True)
    return result


def net_worth(repo: Repository, as_of: str | None = None) -> dict:
    """Patrimônio líquido na data: saldos iniciais + movimentos até `as_of`.

    Sem `as_of`, considera somente transações até hoje (futuras ficam de fora).
    """
    cutoff = as_of or date.today().isoformat()
    total = 0
    accounts = []
    for account in repo.list_accounts():
        balance = account.initial_balance
        for txn in repo.list_transactions(account_id=account.id):
            if txn.date > cutoff:
                continue
            if txn.account_id == account.id:
                balance += txn.amount
            if txn.transfer_account_id == account.id:
                balance -= txn.amount
        accounts.append({"account_id": account.id, "name": account.name, "balance": balance})
        total += balance
    return {"total": total, "accounts": accounts}


def cash_flow(repo: Repository, start: str, end: str) -> list[dict]:
    """Entradas/saídas por mês no período (exclui transferências)."""
    months: dict[str, dict] = {}
    for txn in repo.list_transactions(start=start, end=end):
        if txn.transfer_account_id is not None:
            continue
        key = txn.date[:7]  # AAAA-MM
        bucket = months.setdefault(key, {"month": key, "inflow": 0, "outflow": 0})
        if txn.amount >= 0:
            bucket["inflow"] += txn.amount
        else:
            bucket["outflow"] += abs(txn.amount)
    result = []
    for key in sorted(months):
        bucket = months[key]
        bucket["net"] = bucket["inflow"] - bucket["outflow"]
        result.append(bucket)
    return result


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    total = (year * 12 + (month - 1)) + delta
    return total // 12, (total % 12) + 1


def cash_flow_forecast(repo: Repository, months: int = 12) -> list[dict]:
    """Projeção de fluxo de caixa para os próximos `months` meses."""
    if months < 1:
        months = 1
    if months > 24:
        months = 24
    today = date.today()
    start_year, start_month = today.year, today.month
    first_day = date(start_year, start_month, 1)
    prev_day = first_day - timedelta(days=1)
    starting_balance = net_worth(repo, as_of=prev_day.isoformat())["total"]

    result = []
    cumulative = 0
    for i in range(months):
        y, m = _add_months(start_year, start_month, i)
        start = f"{y:04d}-{m:02d}-01"
        end = f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"
        inflow = 0
        outflow = 0
        for txn in repo.list_transactions(start=start, end=end):
            if txn.transfer_account_id is not None:
                continue
            if txn.amount >= 0:
                inflow += txn.amount
            else:
                outflow += abs(txn.amount)
        net = inflow - outflow
        cumulative += net
        result.append({
            "month": f"{y:04d}-{m:02d}",
            "inflow": inflow,
            "outflow": outflow,
            "net": net,
            "projected_balance": starting_balance + cumulative,
        })
    return result


def income_statement(repo: Repository, start: str, end: str) -> dict:
    """DRE simplificado: receitas, despesas e resultado no período."""
    revenues: dict[int, int] = {}
    expenses: dict[int, int] = {}
    revenue_total = 0
    expense_total = 0
    for txn in repo.list_transactions(start=start, end=end):
        if txn.transfer_account_id is not None:
            continue
        if txn.splits:
            for split in txn.splits:
                cat = repo.get_category(split.category_id) if split.category_id else None
                kind = cat.kind if cat else None
                if kind == "income":
                    revenues[split.category_id] = revenues.get(split.category_id, 0) + split.amount
                    revenue_total += split.amount
                elif kind == "expense":
                    expenses[split.category_id] = (
                        expenses.get(split.category_id, 0) + abs(split.amount)
                    )
                    expense_total += abs(split.amount)
        elif txn.category_id is not None:
            cat = repo.get_category(txn.category_id)
            if cat.kind == "income":
                revenues[txn.category_id] = revenues.get(txn.category_id, 0) + txn.amount
                revenue_total += txn.amount
            elif cat.kind == "expense":
                expenses[txn.category_id] = expenses.get(txn.category_id, 0) + abs(txn.amount)
                expense_total += abs(txn.amount)

    revenue_rows = []
    for cat in repo.list_categories(kind="income"):
        total = revenues.get(cat.id, 0)
        if total:
            revenue_rows.append({"category_id": cat.id, "category": cat.name, "total": total})
    revenue_rows.sort(key=lambda r: r["total"], reverse=True)

    expense_rows = []
    for cat in repo.list_categories(kind="expense"):
        total = expenses.get(cat.id, 0)
        if total:
            expense_rows.append({"category_id": cat.id, "category": cat.name, "total": total})
    expense_rows.sort(key=lambda r: r["total"], reverse=True)

    return {
        "start": start,
        "end": end,
        "revenue_total": revenue_total,
        "expense_total": expense_total,
        "result": revenue_total - expense_total,
        "revenues": revenue_rows,
        "expenses": expense_rows,
    }


def spending_by_cost_center(repo: Repository, start: str, end: str) -> list[dict]:
    """Totais por centro de custo no período (líquido)."""
    totals: dict[int | None, int] = {}
    for txn in repo.list_transactions(start=start, end=end):
        if txn.transfer_account_id is not None:
            continue
        if txn.splits:
            for split in txn.splits:
                key = split.cost_center_id
                totals[key] = totals.get(key, 0) + split.amount
        else:
            key = txn.cost_center_id
            totals[key] = totals.get(key, 0) + txn.amount

    names = {cc.id: cc.name for cc in repo.list_cost_centers()}
    result = []
    for cc_id, total in totals.items():
        if cc_id is None and total == 0:
            continue
        if cc_id is None:
            name = "Sem centro de custo"
        else:
            name = names.get(cc_id, "Sem centro de custo")
        result.append({"cost_center_id": cc_id, "cost_center": name, "total": total})
    result.sort(key=lambda r: abs(r["total"]), reverse=True)
    return result


def dashboard(repo: Repository) -> dict:
    """Painel geral: saldos de todas as contas + resumo de crédito.

    Saldos consideram apenas transações até hoje; `future` traz o efeito líquido
    das transações futuras (não somado ao saldo).
    Crédito: `used` é o valor já utilizado no cartão (saldo negativo vira uso).
    `available` (por conta) = saldo + limite, exibido para todas as contas.
    O resumo de crédito soma todas as contas com `credit_limit > 0` (inclusive
    banco com cheque especial); o saldo de contas não-cartão continua no
    patrimônio.
    """
    accounts = []
    assets_total = 0
    credit = {
        "limit_total": 0,
        "used_total": 0,
        "available_total": 0,
        "accounts": [],
    }
    for account in repo.list_accounts():
        balances = repo.account_balances(account.id)
        balance = balances["balance"]
        entry = {
            "account_id": account.id,
            "name": account.name,
            "type": account.type.value,
            "balance": balance,
            "future": balances["future"],
            "credit_limit": account.credit_limit,
            "available": balance + account.credit_limit,
        }
        is_credit = account.type.value == "credit"
        if account.credit_limit > 0:
            used = (-balance if balance < 0 else 0) if is_credit else 0
            entry.update({
                "credit_limit": account.credit_limit,
                "credit_used": used,
                "credit_available": balance + account.credit_limit,
            })
            credit["limit_total"] += account.credit_limit
            credit["used_total"] += used
            credit["available_total"] += balance + account.credit_limit
            credit["accounts"].append(entry)
        # Cartão com limite entra no resumo de crédito (passivo); demais contas
        # continuam compondo o saldo em contas, mesmo quando têm limite.
        if not (is_credit and account.credit_limit > 0):
            assets_total += balance
        accounts.append(entry)
    return {
        "accounts": accounts,
        "assets_total": assets_total,
        "net_worth": assets_total - credit["used_total"],
        "credit": credit,
    }
