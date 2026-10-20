"""Importação de extratos QIF e OFX (parsers próprios, sem dependências).

Estrutura interna comum:

    ImportedTransaction(date_iso, amount_cents, description, memo, external_id, raw_category)

`amount_cents` é assinado do ponto de vista da conta importada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from money99.domain.money import parse_iso_date


class StatementParseError(ValueError):
    """Erro de parsing de arquivo de extrato."""


@dataclass
class ImportedTransaction:
    date: str  # ISO
    amount: int  # centavos, assinado
    description: str = ""
    memo: str = ""
    external_id: str = ""
    raw_category: str = ""
    tags: list[str] = field(default_factory=list)


# ---------- QIF ----------

def _parse_qif_date(text: str) -> str:
    text = text.strip()
    # QIF usa MM/DD/AAAA (ou apostrofo: 12/31'99). Tambem aceita AAAA-MM-DD.
    normalized = text.replace("'", "/").replace(" ", "")
    parts = re.split(r"[/\-.]", normalized)
    if len(parts) != 3:
        raise StatementParseError(f"data QIF inválida: {text!r}")
    if len(parts[0]) == 4:  # AAAA-MM-DD
        year, month, day = parts
    else:  # MM/DD/AAAA
        month, day, year = parts
    if len(year) == 2:
        year = ("19" if int(year) > 50 else "20") + year
    iso = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    parse_iso_date(iso)
    return iso


def _parse_qif_amount(text: str) -> int:
    text = text.strip().replace("$", "").replace(",", "")
    if not text:
        raise StatementParseError("valor QIF vazio")
    value = float(text)
    return int(round(value * 100))


def parse_qif(content: str) -> list[ImportedTransaction]:
    """Parseia um arquivo QIF (registros !Type:Bank/Cash/CCard)."""
    result: list[ImportedTransaction] = []
    current: dict[str, str] = {}

    def flush():
        if not current:
            return
        if "D" not in current or "T" not in current:
            current.clear()
            return
        result.append(ImportedTransaction(
            date=_parse_qif_date(current["D"]),
            amount=_parse_qif_amount(current["T"]),
            description=current.get("P", "").strip(),
            memo=current.get("M", "").strip(),
            external_id=current.get("N", "").strip(),
            raw_category=current.get("L", "").strip(),
        ))
        current.clear()

    for raw_line in content.splitlines():
        line = raw_line.rstrip("\r\n")
        if not line:
            continue
        if line.startswith("!"):
            flush()
            continue
        code, value = line[0], line[1:].strip()
        if code == "^":
            flush()
            continue
        if code in ("D", "T", "P", "M", "N", "L"):
            current[code] = value
    flush()
    return result


# ---------- OFX ----------

_OFX_TAG = re.compile(r"<(\w+)>([^<\r\n]*)")


def _ofx_date(text: str) -> str:
    # OFX: YYYYMMDDHHMMSS[.sss][tz]
    digits = re.match(r"(\d{8})", text.strip())
    if not digits:
        raise StatementParseError(f"data OFX inválida: {text!r}")
    raw = digits.group(1)
    iso = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    parse_iso_date(iso)
    return iso


def _ofx_amount(text: str) -> int:
    text = text.strip().replace(",", "")
    if not text:
        raise StatementParseError("valor OFX vazio")
    return int(round(float(text) * 100))


def parse_ofx(content: str) -> list[ImportedTransaction]:
    """Parseia OFX (SGML tolerante ou XML) extraindo <STMTTRN>."""
    transactions: list[ImportedTransaction] = []
    # Normaliza SGML->tags reconhecíveis e quebra em blocos
    blocks = re.split(r"</?STMTTRN>", content, flags=re.IGNORECASE)
    for block in blocks[1:]:
        fields: dict[str, str] = {}
        for tag in ("TRNTYPE", "DTPOSTED", "TRNAMT", "FITID", "NAME", "MEMO", "CHECKNUM"):
            match = re.search(
                rf"<{tag}>([^<\r\n]+)", block, flags=re.IGNORECASE
            )
            if match:
                fields[tag] = match.group(1).strip()
        if "DTPOSTED" not in fields or "TRNAMT" not in fields:
            continue
        transactions.append(ImportedTransaction(
            date=_ofx_date(fields["DTPOSTED"]),
            amount=_ofx_amount(fields["TRNAMT"]),
            description=(fields.get("NAME") or fields.get("MEMO") or "").strip(),
            memo=fields.get("MEMO", "").strip(),
            external_id=fields.get("FITID", "").strip(),
        ))
    return transactions


# ---------- dispatch ----------

def parse_statement(content: str, filename: str = "") -> list[ImportedTransaction]:
    """Detecta o formato (OFX por conteúdo, senão QIF) e parseia."""
    head = content[:200].upper()
    lower_name = filename.lower()
    if "<OFX" in head or lower_name.endswith((".ofx", ".qfx")) or "<STMTTRN>" in content.upper():
        return parse_ofx(content)
    if "!TYPE:" in head or lower_name.endswith(".qif"):
        return parse_qif(content)
    raise StatementParseError("formato não reconhecido (esperado QIF ou OFX)")
