"""Relatórios do MEI: faturamento mensal/anual, despesas, lucro e limite anual.

Base: transações do perfil empresarial. Receitas = categorias `kind=income`;
despesas = categorias `kind=expense`. Transferências são ignoradas. Transações
sem categoria não entram nos totais (aparecem como pendentes de categorização).

`monthly_caderno` reproduz as seções do Caderno do MEI (Relatório Mensal das
Receitas Brutas, vendas, despesas, resumo diário e lucro do mês).
"""

from __future__ import annotations

import calendar

MONTH_NAMES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)

ACTIVITY_LINES = {
    "comercio": {
        "label": "COMÉRCIO",
        "line1": (
            "Revenda de mercadorias com dispensa de emissão de documento "
            "fiscal (Vendas para Pessoa Física)"
        ),
        "line2": (
            "Revenda de mercadorias com documento fiscal emitido "
            "(Vendas para empresas – Pessoa Jurídica)"
        ),
        "line3": "Total das receitas com revenda de mercadorias (1 + 2)",
        "numbers": (1, 2, 3),
    },
    "industria": {
        "label": "INDÚSTRIA",
        "line1": (
            "Venda de produtos industrializados com dispensa de emissão de "
            "documento fiscal (Vendas para Pessoa Física)"
        ),
        "line2": (
            "Venda de produtos industrializados com documento fiscal emitido "
            "(Vendas para empresas – Pessoa Jurídica)"
        ),
        "line3": "Total das receitas com venda de produtos industrializados (4 + 5)",
        "numbers": (4, 5, 6),
    },
    "servicos": {
        "label": "SERVIÇOS",
        "line1": (
            "Receita com prestação de serviços com dispensa de emissão de "
            "documento fiscal (Vendas para Pessoa Física)"
        ),
        "line2": (
            "Receita com prestação de serviços com documento fiscal emitido "
            "(Vendas para empresas – Pessoa Jurídica)"
        ),
        "line3": "Total das receitas com prestação de serviços (7 + 8)",
        "numbers": (7, 8, 9),
    },
}


def _txn_amounts(repo) -> tuple[dict[str, dict[str, int]], dict[str, dict]]:
    """Retorna ({AAAAMM: {revenue, expense}}, {AAAAMM: {revenue, expense}})."""
    cat_kind: dict[int | None, str] = {}
    for cat in repo.list_categories():
        cat_kind[cat.id] = cat.kind

    months: dict[str, dict[str, int]] = {}
    for txn in repo.list_transactions():
        if txn.transfer_account_id is not None:
            continue
        key = txn.date[:7]
        bucket = months.setdefault(key, {"revenue": 0, "expense": 0})
        if txn.splits:
            for split in txn.splits:
                kind = cat_kind.get(split.category_id)
                if kind == "income":
                    bucket["revenue"] += split.amount
                elif kind == "expense":
                    bucket["expense"] += abs(split.amount)
        elif txn.category_id is not None:
            kind = cat_kind.get(txn.category_id)
            if kind == "income":
                bucket["revenue"] += txn.amount
            elif kind == "expense":
                bucket["expense"] += abs(txn.amount)
    return months, cat_kind


def monthly_report(repo, year: int) -> dict:
    """Relatório MEI do ano: linhas mensais + totais + uso do limite anual."""
    months, _ = _txn_amounts(repo)
    lines = []
    revenue_total = 0
    expense_total = 0
    for month in range(1, 13):
        key = f"{year}-{month:02d}"
        bucket = months.get(key, {"revenue": 0, "expense": 0})
        revenue = bucket["revenue"]
        expense = bucket["expense"]
        revenue_total += revenue
        expense_total += expense
        lines.append({
            "month": month,
            "key": key,
            "revenue": revenue,
            "expense": expense,
            "result": revenue - expense,
        })

    profile = repo.get_profile(repo.profile_id) if repo.profile_id else None
    annual_limit = profile.annual_limit if profile else 0
    used_pct = round((revenue_total / annual_limit) * 100) if annual_limit else 0
    return {
        "year": year,
        "months": lines,
        "revenue_total": revenue_total,
        "expense_total": expense_total,
        "result_total": revenue_total - expense_total,
        "annual_limit": annual_limit,
        "limit_used_pct": used_pct,
        "limit_remaining": annual_limit - revenue_total,
        "limit_exceeded": annual_limit > 0 and revenue_total > annual_limit,
    }


def monthly_caderno(repo, year: int, month: int) -> dict:
    """Dados do mês no formato do Caderno do MEI (páginas de controle + DASN)."""
    if not 1 <= month <= 12:
        raise ValueError("mês inválido")

    profile = repo.get_profile(repo.profile_id) if repo.profile_id else None
    activity = getattr(profile, "activity", None)
    activity = getattr(activity, "value", activity) or "servicos"
    if activity not in ACTIVITY_LINES:
        activity = "servicos"

    cat_kind: dict[int | None, str] = {}
    for cat in repo.list_categories():
        cat_kind[cat.id] = cat.kind

    key = f"{year}-{month:02d}"
    last_day = calendar.monthrange(year, month)[1]
    daily = [
        {"day": day, "sales": 0, "expenses": 0}
        for day in range(1, last_day + 1)
    ]
    sales: list[dict] = []
    expenses: list[dict] = []

    for txn in repo.list_transactions(
        start=f"{key}-01", end=f"{key}-{last_day:02d}"
    ):
        if txn.transfer_account_id is not None:
            continue
        income = 0
        expense = 0
        if txn.splits:
            for split in txn.splits:
                kind = cat_kind.get(split.category_id)
                if kind == "income":
                    income += split.amount
                elif kind == "expense":
                    expense += abs(split.amount)
        elif txn.category_id is not None:
            kind = cat_kind.get(txn.category_id)
            if kind == "income":
                income = txn.amount
            elif kind == "expense":
                expense = abs(txn.amount)

        try:
            day = int(txn.date[8:10])
        except ValueError:
            day = 0
        if income:
            sales.append({
                "date": txn.date,
                "description": txn.description,
                "amount": income,
                "doc_issued": bool(txn.doc_issued),
            })
            if 1 <= day <= last_day:
                daily[day - 1]["sales"] += income
        if expense:
            expenses.append({
                "date": txn.date,
                "description": txn.description,
                "amount": expense,
            })
            if 1 <= day <= last_day:
                daily[day - 1]["expenses"] += expense

    sales.sort(key=lambda item: (item["date"], item["description"]))
    expenses.sort(key=lambda item: (item["date"], item["description"]))

    sales_total = sum(item["amount"] for item in sales)
    with_doc = sum(item["amount"] for item in sales if item["doc_issued"])
    without_doc = sales_total - with_doc
    expenses_total = sum(item["amount"] for item in expenses)

    spec = ACTIVITY_LINES[activity]
    n1, n2, n3 = spec["numbers"]
    lines = [
        {"number": n1, "label": spec["line1"], "amount": without_doc},
        {"number": n2, "label": spec["line2"], "amount": with_doc},
        {
            "number": n3,
            "label": spec["line3"],
            "amount": sales_total,
            "total": True,
        },
    ]

    return {
        "year": year,
        "month": month,
        "month_key": key,
        "month_name": MONTH_NAMES[month - 1],
        "period_label": f"01/{month:02d}/{year} a {last_day:02d}/{month:02d}/{year}",
        "activity": activity,
        "activity_label": spec["label"],
        "lines": lines,
        "sales": sales,
        "expenses": expenses,
        "sales_total": sales_total,
        "sales_with_doc": with_doc,
        "sales_without_doc": without_doc,
        "expenses_total": expenses_total,
        "profit": sales_total - expenses_total,
        "daily": daily,
        "daily_sales": sum(item["sales"] for item in daily),
        "daily_expenses": sum(item["expenses"] for item in daily),
    }


def period_report(repo, start: str, end: str) -> dict:
    """Totais de receitas/despesas/resultado num período arbitrário."""
    months, _ = _txn_amounts(repo)
    revenue = 0
    expense = 0
    for key, bucket in months.items():
        first = f"{key}-01"
        last = f"{key}-31"
        if last < start or first > end:
            continue
        revenue += bucket["revenue"]
        expense += bucket["expense"]
    return {
        "start": start,
        "end": end,
        "revenue": revenue,
        "expense": expense,
        "result": revenue - expense,
    }
