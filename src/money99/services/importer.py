"""Importação de extratos QIF e OFX (parsers próprios, sem dependências).

Estrutura interna comum:

    ImportedTransaction(date_iso, amount_cents, description, memo, external_id, raw_category)

`amount_cents` é assinado do ponto de vista da conta importada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from money99.domain.money import parse_iso_date


class StatementParseError(ValueError):
    """Erro de parsing de arquivo de extrato."""


def _norm(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


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
        description = _norm(current.get("P", ""))
        memo = _norm(current.get("M", ""))
        if memo and description and memo not in description:
            description = f"{description} {memo}"
        elif memo and not description:
            description = memo
        result.append(ImportedTransaction(
            date=_parse_qif_date(current["D"]),
            amount=_parse_qif_amount(current["T"]),
            description=description,
            memo="",
            external_id=_norm(current.get("N", "")),
            raw_category=_norm(current.get("L", "")),
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
        name = _norm(fields.get("NAME") or "")
        memo = _norm(fields.get("MEMO") or "")
        description = name or memo
        if memo and description and memo not in description:
            description = f"{description} {memo}"
        transactions.append(ImportedTransaction(
            date=_ofx_date(fields["DTPOSTED"]),
            amount=_ofx_amount(fields["TRNAMT"]),
            description=description,
            memo="",
            external_id=_norm(fields.get("FITID", "")),
        ))
    return transactions


# ---------- texto colado (banco) ----------

def _parse_br_money(text: str) -> int:
    value = text.strip()
    if not value:
        raise StatementParseError("valor do extrato vazio")
    value = value.replace("-", "")
    value = value.replace("R$", "", 1).replace(" ", "")
    value = value.replace(".", "").replace(",", ".")
    try:
        cents = (Decimal(value) * 100).quantize(Decimal("1"))
    except InvalidOperation as exc:
        raise StatementParseError(f"valor monetário inválido: {text!r}") from exc
    return int(cents)


def _parse_pasted_date(text: str) -> str:
    value = text.strip()
    match = re.search(r"\d{2}/\d{2}/\d{4}", value)
    if not match:
        raise StatementParseError(f"data do extrato inválida: {text!r}")
    raw = match.group(0)
    day, month, year = raw.split("/")
    iso = f"{year}-{month}-{day}"
    parse_iso_date(iso)
    return iso


def parse_pasted_text(content: str) -> list[ImportedTransaction]:
    """Parseia texto colado em formato bancário do tipo Data / Descrição / Valor / Saldo."""
    rows: list[ImportedTransaction] = []
    for raw_line in content.splitlines():
        line = " ".join(raw_line.strip().split())
        if not line:
            continue
        lower = line.lower()
        if (
            lower.startswith("data")
            or lower.startswith("descrição")
            or lower.startswith("valor")
            or lower.startswith("saldo")
        ):
            continue
        if not re.search(r"\d{2}/\d{2}/\d{4}", line):
            continue
        date_match = re.search(r"\d{2}/\d{2}/\d{4}", line)
        date = _parse_pasted_date(date_match.group(0))
        body = line[date_match.end():].strip()
        amount_match = re.search(
            r"(?P<sign>-)?(?:R\$\s*)?(?P<value>\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})",
            body,
            flags=re.IGNORECASE,
        )
        if not amount_match:
            continue
        amount_raw = amount_match.group(0)
        amount_value = _parse_br_money(amount_raw)
        sign = -1 if amount_match.group("sign") == "-" else 1
        amount = sign * amount_value
        before = _norm(body[:amount_match.start()].strip().rstrip("-").strip())
        after = _norm(body[amount_match.end():].strip())
        after = re.sub(
            r"^(?:R\$\s*)?[\d]{1,3}(?:\.\d{3})*,\d{2}\s*",
            "",
            after,
            count=1,
            flags=re.IGNORECASE,
        ).strip()
        after = _norm(after)
        description = before
        if after and after not in description:
            description = f"{description} {after}".strip()
        if not before:
            continue
        rows.append(ImportedTransaction(
            date=date,
            amount=amount,
            description=description,
            memo="",
        ))
    if not rows:
        raise StatementParseError("formato de texto colado não reconhecido")
    return rows

# ---------- dispatch ----------

def parse_statement(content: str, filename: str = "") -> list[ImportedTransaction]:
    """Detecta o formato (OFX, QIF ou texto colado em extrato bancário) e parseia."""
    head = content[:200].upper()
    lower_name = filename.lower()
    if "<OFX" in head or lower_name.endswith((".ofx", ".qfx")) or "<STMTTRN>" in content.upper():
        return parse_ofx(content)
    if "!TYPE:" in head or lower_name.endswith(".qif"):
        return parse_qif(content)
    if re.search(r"\d{2}/\d{2}/\d{4}", content):
        return parse_pasted_text(content)
    raise StatementParseError("formato não reconhecido (esperado QIF, OFX ou texto colado)")
