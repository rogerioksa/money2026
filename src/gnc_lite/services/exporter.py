"""Exportacao de lancamentos (CSV) e relatorios (HTML/PDF)."""

from __future__ import annotations

import csv
import html
import io
from pathlib import Path

from gnc_lite.domain.money import Money
from gnc_lite.services.ledger import Ledger
from gnc_lite.services.reports import Report

CSV_COLUMNS = ("ref", "date", "description", "payee", "account", "amount", "memo")


# ------------------------------------------------------------------ lancamentos
def transactions_to_csv(ledger: Ledger) -> str:
    """Serializa todos os lancamentos como CSV (uma linha por partida)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for index, transaction in enumerate(ledger.transactions(), start=1):
        for split in transaction.splits:
            writer.writerow(
                [
                    index,
                    transaction.date.isoformat(),
                    transaction.description,
                    transaction.payee,
                    split.account.code,
                    f"{split.amount.amount}",
                    split.memo,
                ]
            )
    return buffer.getvalue()


def write_transactions_csv(ledger: Ledger, path: str | Path) -> Path:
    target = Path(path)
    target.write_text(transactions_to_csv(ledger), encoding="utf-8")
    return target


# -------------------------------------------------------------------- relatorios
def _cell(value: object) -> str:
    if isinstance(value, Money):
        text = f"{value.amount:,.2f}"
        text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
        return text
    return "" if value is None else str(value)


def _is_total(value: object) -> bool:
    return isinstance(value, str) and value.upper().startswith("TOTAL")


def _html_row(row: tuple[object, ...], *, bold: bool) -> str:
    weight = "bold" if bold else "normal"
    cells = "".join(
        f"<td style='font-weight:{weight};'>{html.escape(_cell(value))}</td>" for value in row
    )
    return f"<tr>{cells}</tr>"


def report_to_html(report: Report) -> str:
    """Converte um relatorio em HTML (usado tambem para gerar o PDF)."""
    parts = [f"<h2>{html.escape(report.title)}</h2>"]
    if report.info:
        info = "<br>".join(
            f"<b>{html.escape(label)}:</b> {html.escape(value)}" for label, value in report.info
        )
        parts.append(f"<p>{info}</p>")
    if report.period:
        parts.append(f"<p>{html.escape(report.period)}</p>")
    style = "border-collapse:collapse"
    parts.append(f"<table border='1' cellspacing='0' cellpadding='4' style='{style}'>")
    parts.append(
        "<tr>" + "".join(f"<th>{html.escape(name)}</th>" for name in report.columns) + "</tr>"
    )
    for row in report.rows:
        section = len(row) >= 1 and all(value is None for value in row[1:])
        parts.append(_html_row(row, bold=_is_total(row[0]) or section))
    if report.footer is not None:
        parts.append(_html_row(report.footer, bold=True))
    parts.append("</table>")
    if report.notes:
        notes = "<br>".join(html.escape(note) for note in report.notes)
        parts.append(f"<p style='font-size:8pt;color:#555;'>{notes}</p>")
    return "".join(parts)


def write_report_pdf(report: Report, path: str | Path) -> Path:
    """Gera um PDF do relatorio via reportlab (sem Qt/Flet)."""
    from gnc_lite.services.pdf import report_to_pdf

    return report_to_pdf(report, Path(path))
