"""Indicadores e sugestões do painel.

Reúne o fluxo do mês (receitas, despesas, resultado e taxa de poupança),
a posição de títulos a pagar/receber, lançamentos futuros e uma lista de
sugestões priorizadas com ações para o usuário.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from money99.db.repository import Repository
from money99.domain.money import format_brl
from money99.services.budget import budget_alerts
from money99.services.reports import (
    cash_flow_forecast,
    dashboard,
    spending_by_category,
)

# Aumento mínimo para sugerir atenção a uma categoria: R$ 50,00 e 20%.
_CATEGORY_DELTA_MIN = 5000
_CATEGORY_CHANGE_MIN = 20
_MAX_SUGGESTIONS = 8


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    last_day = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _plural(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural


def _pct_change(current: int, previous: int) -> int | None:
    if previous <= 0:
        return None
    return int(round((current - previous) * 100 / previous))


def _month_flow(repo: Repository, start: str, end: str) -> dict:
    """Entradas/saídas do período (transferências não entram no fluxo)."""
    income = 0
    expense = 0
    uncategorized_count = 0
    uncategorized_amount = 0
    unreconciled_count = 0
    for txn in repo.list_transactions(start=start, end=end):
        if txn.transfer_account_id is not None:
            continue
        if txn.amount >= 0:
            income += txn.amount
        else:
            expense -= txn.amount
        if not txn.reconciled:
            unreconciled_count += 1
        if txn.category_id is None and not txn.splits:
            uncategorized_count += 1
            uncategorized_amount += abs(txn.amount)
    return {
        "income": income,
        "expense": expense,
        "result": income - expense,
        "uncategorized_count": uncategorized_count,
        "uncategorized_amount": uncategorized_amount,
        "unreconciled_count": unreconciled_count,
    }


def _category_increases(
    repo: Repository, start: str, end: str, prev_start: str, prev_end: str
) -> list[dict]:
    current = spending_by_category(repo, start, end)
    previous = {
        row["category_id"]: row["total"]
        for row in spending_by_category(repo, prev_start, prev_end)
    }
    increases = []
    for row in current:
        prev_total = previous.get(row["category_id"], 0)
        if prev_total <= 0:
            continue
        delta = row["total"] - prev_total
        if delta < _CATEGORY_DELTA_MIN:
            continue
        change = int(round(delta * 100 / prev_total))
        if change < _CATEGORY_CHANGE_MIN:
            continue
        increases.append({
            "category_id": row["category_id"],
            "category": row["category"],
            "current": row["total"],
            "previous": prev_total,
            "change": change,
        })
    increases.sort(key=lambda row: row["current"] - row["previous"], reverse=True)
    return increases


def _titles_summary(repo: Repository) -> dict:
    today = date.today()
    today_iso = today.isoformat()
    upcoming_iso = (today + timedelta(days=7)).isoformat()
    summary = {
        "payable_open": 0,
        "payable_count": 0,
        "receivable_open": 0,
        "receivable_count": 0,
        "overdue_amount": 0,
        "overdue_count": 0,
        "upcoming_amount": 0,
        "upcoming_count": 0,
    }
    for title in repo.list_titles():
        if title.status not in ("open", "partial"):
            continue
        remaining = title.amount - max(0, title.paid_amount)
        if remaining <= 0:
            continue
        if title.type == "payable":
            summary["payable_open"] += remaining
            summary["payable_count"] += 1
        else:
            summary["receivable_open"] += remaining
            summary["receivable_count"] += 1
        if title.due_date < today_iso:
            summary["overdue_amount"] += remaining
            summary["overdue_count"] += 1
        elif title.due_date <= upcoming_iso:
            summary["upcoming_amount"] += remaining
            summary["upcoming_count"] += 1
    return summary


def _future_summary(repo: Repository) -> dict:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    net = 0
    count = 0
    for txn in repo.list_transactions(start=tomorrow):
        count += 1
        # Transferência entre contas próprias não altera o patrimônio.
        if txn.transfer_account_id is None:
            net += txn.amount
    return {"net": net, "count": count}


def _suggestion(
    level: str, title: str, detail: str, href: str, action: str
) -> dict:
    return {
        "level": level,
        "title": title,
        "detail": detail,
        "href": href,
        "action": action,
    }


def _build_suggestions(
    repo: Repository,
    year: int,
    month: int,
    flow: dict,
    titles: dict,
    credit_pct: int,
    increases: list[dict],
    negative_forecast: dict | None,
) -> list[dict]:
    suggestions: list[dict] = []

    if titles["overdue_count"] > 0:
        count = titles["overdue_count"]
        suggestions.append(_suggestion(
            "danger",
            f"{count} {_plural(count, 'título vencido', 'títulos vencidos')}",
            f"{format_brl(titles['overdue_amount'], with_symbol=True)} em atraso. "
            "Quite ou renegocie para evitar juros e multas.",
            "#/carcap",
            "Ver títulos vencidos",
        ))

    if credit_pct >= 90:
        suggestions.append(_suggestion(
            "danger",
            "Crédito quase esgotado",
            f"{credit_pct}% do limite já foi usado. Evite novos parcelamentos "
            "até reduzir o saldo.",
            "#/contas",
            "Revisar contas e limites",
        ))
    elif credit_pct >= 70:
        suggestions.append(_suggestion(
            "warning",
            "Uso alto do crédito",
            f"{credit_pct}% do limite está comprometido. Segure novos gastos no cartão.",
            "#/contas",
            "Acompanhar limite",
        ))

    overruns = sorted(
        budget_alerts(repo, year, month)["monthly"],
        key=lambda row: row["over"],
        reverse=True,
    )
    if overruns:
        total_over = sum(row["over"] for row in overruns)
        names = ", ".join(row["category"] for row in overruns[:3])
        if len(overruns) > 3:
            names += f" e mais {len(overruns) - 3}"
        suggestions.append(_suggestion(
            "danger" if len(overruns) >= 3 else "warning",
            f"{len(overruns)} "
            f"{_plural(len(overruns), 'orçamento estourado', 'orçamentos estourados')}",
            f"{format_brl(total_over, with_symbol=True)} acima do planejado em {names}.",
            "#/orcamento",
            "Revisar orçamento",
        ))

    if flow["result"] < 0:
        suggestions.append(_suggestion(
            "warning",
            "Mês no vermelho",
            f"As despesas passaram as receitas em "
            f"{format_brl(-flow['result'], with_symbol=True)}.",
            "#/relatorios",
            "Analisar o mês",
        ))

    if increases:
        top = increases[0]
        detail = (
            f"{top['category']} subiu {top['change']}% "
            f"({format_brl(top['previous'], with_symbol=True)} → "
            f"{format_brl(top['current'], with_symbol=True)})."
        )
        if len(increases) > 1:
            detail += f" Outros {len(increases) - 1} gasto(s) também aumentaram."
        suggestions.append(_suggestion(
            "warning" if top["change"] >= 50 else "info",
            "Gastos em alta",
            detail,
            "#/relatorios",
            "Comparar categorias",
        ))

    if negative_forecast is not None:
        forecast_month = negative_forecast["month"]
        suggestions.append(_suggestion(
            "warning",
            "Projeção de saldo negativa",
            f"Com os lançamentos futuros, o saldo pode chegar a "
            f"{format_brl(negative_forecast['projected_balance'], with_symbol=True)} "
            f"em {forecast_month[5:7]}/{forecast_month[:4]}.",
            "#/relatorios",
            "Ver projeção",
        ))

    savings_rate = flow["savings_rate"]
    if savings_rate is not None and flow["result"] >= 0 and savings_rate < 10:
        suggestions.append(_suggestion(
            "info",
            "Poupança abaixo da meta",
            f"Você guardou {savings_rate}% das receitas do mês. "
            "Uma reserva de 10% ou mais dá mais fôlego financeiro.",
            "#/orcamento",
            "Planejar o mês",
        ))

    if titles["upcoming_count"] > 0:
        count = titles["upcoming_count"]
        suggestions.append(_suggestion(
            "info",
            f"{count} {_plural(count, 'título vence', 'títulos vencem')} em 7 dias",
            f"Somam {format_brl(titles['upcoming_amount'], with_symbol=True)} "
            "em contas a pagar e a receber.",
            "#/carcap",
            "Ver próximos vencimentos",
        ))

    if flow["uncategorized_count"] > 0:
        count = flow["uncategorized_count"]
        label = _plural(
            count, "lançamento sem categoria", "lançamentos sem categoria"
        )
        suggestions.append(_suggestion(
            "info",
            f"{count} {label}",
            f"{format_brl(flow['uncategorized_amount'], with_symbol=True)} ainda "
            "sem classificação. Categorizar melhora o orçamento e os relatórios.",
            "#/extrato",
            "Categorizar lançamentos",
        ))

    if flow["unreconciled_count"] > 0:
        count = flow["unreconciled_count"]
        label = _plural(
            count, "lançamento não conciliado", "lançamentos não conciliados"
        )
        suggestions.append(_suggestion(
            "info",
            f"{count} {label}",
            "Confira os valores no extrato para manter os saldos auditáveis.",
            "#/extrato",
            "Conciliar extrato",
        ))

    return suggestions[:_MAX_SUGGESTIONS]


def dashboard_insights(
    repo: Repository,
    year: int,
    month: int,
    dashboard_data: dict | None = None,
) -> dict:
    """Indicadores do mês e sugestões priorizadas para o painel.

    `dashboard_data` evita recalcular saldos quando o chamador já executou
    `dashboard(repo)`; sem ele, o resumo de crédito é obtido internamente.
    """
    start, end = _month_bounds(year, month)
    prev_year, prev_month = _previous_month(year, month)
    prev_start, prev_end = _month_bounds(prev_year, prev_month)

    flow = _month_flow(repo, start, end)
    previous_flow = _month_flow(repo, prev_start, prev_end)
    flow["savings_rate"] = (
        int(round(flow["result"] * 100 / flow["income"]))
        if flow["income"] > 0
        else None
    )
    flow["prev_income"] = previous_flow["income"]
    flow["prev_expense"] = previous_flow["expense"]
    flow["prev_result"] = previous_flow["result"]
    flow["income_change"] = _pct_change(flow["income"], previous_flow["income"])
    flow["expense_change"] = _pct_change(flow["expense"], previous_flow["expense"])

    titles = _titles_summary(repo)
    future = _future_summary(repo)

    if dashboard_data is None:
        dashboard_data = dashboard(repo)
    credit = dashboard_data["credit"]
    limit_total = credit["limit_total"]
    used_total = credit["used_total"]
    credit_pct = (used_total * 100) // limit_total if limit_total > 0 else 0

    increases = _category_increases(repo, start, end, prev_start, prev_end)
    negative_forecast = next(
        (row for row in cash_flow_forecast(repo, 3) if row["projected_balance"] < 0),
        None,
    )

    suggestions = _build_suggestions(
        repo, year, month, flow, titles, credit_pct, increases, negative_forecast
    )

    return {
        "year": year,
        "month": month,
        "flow": flow,
        "titles": titles,
        "future": future,
        "credit": {"used_pct": credit_pct},
        "category_increases": increases,
        "suggestions": suggestions,
    }
