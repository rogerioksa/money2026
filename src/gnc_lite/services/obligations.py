"""Obrigacoes mensais e anuais do MEI.

- DAS: guia unica mensal (INSS + ICMS/ISS), vencimento dia 20.
- RMR: Relatorio Mensal de Receitas Brutas, ate dia 20 (guardado com as notas).
- DASN-SIMEI: declaracao anual do faturamento do ano anterior, ate 31/05.

O cumprimento (pago/arquivado) e registrado pelo usuario em um sidecar JSON
do banco da empresa; os valores de receita vêm dos lancamentos.
"""

from __future__ import annotations

import calendar
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from gnc_lite.config import AppConfig
from gnc_lite.domain.money import Money
from gnc_lite.services import mei
from gnc_lite.services.ledger import Ledger

STATUS_DONE = "concluida"
STATUS_PENDING = "pendente"
STATUS_OVERDUE = "atrasada"

STATUS_LABEL = {
    STATUS_DONE: "Paga",
    STATUS_PENDING: "Pendente",
    STATUS_OVERDUE: "Atrasada",
}


@dataclass
class Obligation:
    """Uma obrigacao de uma competencia."""

    key: str
    kind: str  # das | rmr | dasn
    title: str
    period: str
    due: date
    status: str
    detail: str
    amount_minor: int | None = None


def records_path(db_path: str | Path) -> Path:
    return Path(db_path).with_suffix(".obrigacoes.json")


def load_records(db_path: str | Path) -> dict[str, dict]:
    target = records_path(db_path)
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_records(db_path: str | Path, records: dict[str, dict]) -> None:
    target = records_path(db_path)
    target.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def mark(db_path: str | Path, key: str, done: bool) -> dict[str, dict]:
    records = load_records(db_path)
    if done:
        records[key] = {"done": True, "at": date.today().isoformat()}
    else:
        records.pop(key, None)
    save_records(db_path, records)
    return records


def _brl(value: Money) -> str:
    return f"R$ {value.amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _month_revenue(ledger: Ledger, year: int, month: int) -> Money:
    last_day = calendar.monthrange(year, month)[1]
    entries = mei.revenue_entries(ledger, date(year, month, 1), date(year, month, last_day))
    total = Money.zero()
    for entry in entries:
        total = total + entry.value
    return total


def _year_revenue(ledger: Ledger, year: int) -> Money:
    entries = mei.revenue_entries(ledger, date(year, 1, 1), date(year, 12, 31))
    total = Money.zero()
    for entry in entries:
        total = total + entry.value
    return total


def _status(key: str, due: date, records: dict[str, dict], today: date) -> str:
    if records.get(key, {}).get("done"):
        return STATUS_DONE
    if today > due:
        return STATUS_OVERDUE
    return STATUS_PENDING


def compute(
    ledger: Ledger,
    config: AppConfig,
    year: int,
    month: int,
    db_path: str | Path,
    today: date | None = None,
) -> list[Obligation]:
    """Obrigacoes da competencia mensal + DASN do ano anterior."""
    today = today or date.today()
    records = load_records(db_path)
    return compute_with_records(ledger, config, year, month, records, today)


def compute_with_records(
    ledger: Ledger,
    config: AppConfig,
    year: int,
    month: int,
    records: dict[str, dict],
    today: date,
) -> list[Obligation]:
    period = f"{month:02d}/{year}"
    due_monthly = date(year, month, 20)
    revenue = _month_revenue(ledger, year, month)

    das_key = f"das:{year}-{month:02d}"
    rmr_key = f"rmr:{year}-{month:02d}"
    items = [
        Obligation(
            key=das_key,
            kind="das",
            title="DAS — Guia mensal",
            period=period,
            due=due_monthly,
            status=_status(das_key, due_monthly, records, today),
            detail=(
                "Guia única (INSS + ICMS/ISS). "
                "Emita no Portal do Simples e marque como paga aqui."
            ),
        ),
        Obligation(
            key=rmr_key,
            kind="rmr",
            title="RMR — Receitas Brutas do mês",
            period=period,
            due=due_monthly,
            status=_status(rmr_key, due_monthly, records, today),
            detail=(
                f"Receita lançada no mês: {_brl(revenue)}. "
                "Gere o relatório em Relatórios → MEI mensal e guarde com as notas."
            ),
            amount_minor=revenue.minor_units,
        ),
    ]

    prev = year - 1
    dasn_key = f"dasn:{prev}"
    dasn_due = date(year, 5, 31)
    annual = _year_revenue(ledger, prev)
    limit = mei.effective_annual_limit(config, prev)
    pct = (annual.minor_units / limit.minor_units * 100) if limit.minor_units else 0
    pct_text = f"{pct:.1f}".replace(".", ",")
    items.append(
        Obligation(
            key=dasn_key,
            kind="dasn",
            title=f"DASN-SIMEI {prev}",
            period=str(prev),
            due=dasn_due,
            status=_status(dasn_key, dasn_due, records, today),
            detail=(
                f"Faturamento de {prev}: {_brl(annual)} "
                f"({pct_text}% do limite de {_brl(limit)}). "
                "Envie à Receita até 31/05 e marque como entregue."
            ),
            amount_minor=annual.minor_units,
        )
    )
    return items


def das_csv_text(
    ledger: Ledger,
    config: AppConfig,
    year: int,
    records: dict[str, dict],
    today: date,
) -> str:
    """Lista dos DAS do ano em CSV (ponto e virgula, pronto p/ Excel)."""
    lines = ["Competência;Vencimento;Situação;Detalhe"]
    for month in range(1, 13):
        items = compute_with_records(ledger, config, year, month, records, today)
        das = next(item for item in items if item.kind == "das")
        lines.append(
            ";".join(
                [
                    das.period,
                    das.due.strftime("%d/%m/%Y"),
                    STATUS_LABEL.get(das.status, das.status),
                    das.detail,
                ]
            )
        )
    return "\ufeff" + "\n".join(lines) + "\n"
