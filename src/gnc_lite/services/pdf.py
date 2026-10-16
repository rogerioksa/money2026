"""Geracao de PDF de relatorios sem depender do Qt (usa reportlab)."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from gnc_lite.domain.money import Money
from gnc_lite.services.reports import Report

_HEADER_BG = colors.HexColor("#4F46E5")
_ROW_BG = colors.HexColor("#EEF2FF")
_TOTAL_BG = colors.HexColor("#E0E7FF")


def _cell_text(value: object) -> str:
    if isinstance(value, Money):
        return f"{value.amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "" if value is None else str(value)


def _is_section(row: tuple[object, ...]) -> bool:
    return len(row) >= 1 and all(value is None for value in row[1:])


def _is_total(value: object) -> bool:
    return isinstance(value, str) and value.upper().startswith(("TOTAL", "RECEITA BRUTA"))


def report_to_pdf(report: Report, path: str | Path) -> Path:
    """Escreve um relatorio em PDF e devolve o caminho gerado."""
    target = Path(path)
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(
        str(target),
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=report.title,
    )

    story: list = [Paragraph(report.title, styles["Title"])]
    if report.info:
        info_html = " &nbsp;&nbsp; ".join(
            f"<b>{label}:</b> {value}" for label, value in report.info
        )
        story.append(Paragraph(info_html, styles["Normal"]))
    if report.period:
        story.append(Paragraph(report.period, styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    data: list[list[str]] = [[_cell_text(name) for name in report.columns]]
    style_commands: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C7D2FE")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]

    max_columns = len(report.columns)
    for row in report.rows:
        values = [_cell_text(value) for value in row]
        values += [""] * (max_columns - len(values))
        index = len(data)
        data.append(values)
        if _is_section(row) or _is_total(row[0]):
            style_commands.append(("FONTNAME", (0, index), (-1, index), "Helvetica-Bold"))
            style_commands.append(("BACKGROUND", (0, index), (-1, index), _TOTAL_BG))
        elif index % 2 == 0:
            style_commands.append(("BACKGROUND", (0, index), (-1, index), _ROW_BG))

    if report.footer is not None:
        values = [_cell_text(value) for value in report.footer]
        values += [""] * (max_columns - len(values))
        index = len(data)
        data.append(values)
        style_commands.append(("FONTNAME", (0, index), (-1, index), "Helvetica-Bold"))
        style_commands.append(("BACKGROUND", (0, index), (-1, index), _TOTAL_BG))

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle(style_commands))
    story.append(table)

    for note in report.notes:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(note, styles["Italic"]))

    document.build(story)
    return target
