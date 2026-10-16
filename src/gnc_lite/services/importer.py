"""Importacao de lancamentos de arquivos CSV, QIF e OFX."""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from gnc_lite.domain.account import Account
from gnc_lite.domain.errors import GncLiteError
from gnc_lite.domain.money import money
from gnc_lite.domain.transaction import Split, Transaction
from gnc_lite.services.ledger import Ledger


class ImportParseError(GncLiteError):
    """Arquivo de importacao invalido."""


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d/%m/%y", "%m/%d/%y")


def _parse_date(text: str) -> date:
    cleaned = (text or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return date.fromisoformat(cleaned) if fmt == "%Y-%m-%d" else _strptime(cleaned, fmt)
        except ValueError:
            continue
    raise ImportParseError(f"Data invalida: {text!r}")


def _strptime(text: str, fmt: str) -> date:
    from datetime import datetime

    return datetime.strptime(text, fmt).date()


def _parse_amount(text: str) -> Decimal:
    cleaned = (text or "").strip().replace(" ", "")
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ImportParseError(f"Valor invalido: {text!r}") from exc


def _resolve_account(ledger: Ledger, reference: str) -> Account | None:
    text = (reference or "").strip().strip("[]").strip()
    if not text:
        return None
    account = ledger.repo.get_account_by_code(text)
    if account is not None:
        return account
    for candidate in ledger.list_accounts():
        if candidate.name.lower() == text.lower():
            return candidate
    return None


# ------------------------------------------------------------------------- CSV
CSV_COLUMNS = ("ref", "date", "description", "payee", "account", "amount", "memo")


def read_transactions_csv(ledger: Ledger, text: str) -> list[Transaction]:
    """Le um CSV (uma linha por partida, agrupadas por ``ref``)."""
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = set(reader.fieldnames or [])
    if not {"ref", "date", "account", "amount"} <= fieldnames:
        raise ImportParseError("CSV precisa das colunas ref, date, account e amount")

    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for row in reader:
        ref = (row.get("ref") or "").strip()
        if ref not in groups:
            groups[ref] = []
            order.append(ref)
        groups[ref].append(row)

    transactions: list[Transaction] = []
    for ref in order:
        rows = groups[ref]
        first = rows[0]
        splits: list[Split] = []
        for row in rows:
            account = ledger.repo.get_account_by_code((row.get("account") or "").strip())
            if account is None:
                raise ImportParseError(f"Conta nao encontrada: {row.get('account')!r}")
            amount = money(_parse_amount(row.get("amount") or "0"))
            memo = (row.get("memo") or "").strip()
            splits.append(Split(account, amount, memo))
        transactions.append(
            Transaction(
                date=_parse_date(first.get("date") or ""),
                description=(first.get("description") or "").strip(),
                payee=(first.get("payee") or "").strip(),
                splits=splits,
            )
        )
    return transactions


# ------------------------------------------------------------------------- QIF
_BLOCK_SEPARATOR = "^"


def _qif_records(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if not line or line.startswith("!"):
            continue
        if line.startswith(_BLOCK_SEPARATOR):
            if current:
                records.append(current)
                current = {}
            continue
        code, value = line[0], line[1:].strip()
        current[code] = value
    if current:
        records.append(current)
    return records


def read_qif(ledger: Ledger, text: str, account: Account) -> list[Transaction]:
    """Le um arquivo QIF, lancando contra a conta informada."""
    transactions: list[Transaction] = []
    for record in _qif_records(text):
        if "T" not in record:
            continue
        amount = money(_parse_amount(record["T"]))
        category_reference = record.get("L")
        counter = _resolve_account(ledger, category_reference) if category_reference else None
        if counter is None:
            raise ImportParseError(f"Categoria nao encontrada no QIF: {category_reference!r}")
        transactions.append(
            Transaction(
                date=_parse_date(record.get("D", "")),
                description=record.get("P", ""),
                payee=record.get("P", ""),
                memo=record.get("M", ""),
                splits=[Split(account, amount, record.get("M", "")), Split(counter, -amount)],
            )
        )
    return transactions


# ------------------------------------------------------------------------- OFX
_STMT_RE = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.IGNORECASE | re.DOTALL)


def _ofx_tag(block: str, tag: str) -> str | None:
    match = re.search(rf"<{tag}>([^<\r\n]*)", block, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _parse_ofx_date(text: str) -> date:
    digits = "".join(ch for ch in text if ch.isdigit())[:8]
    return date(int(digits[0:4]), int(digits[4:6]), int(digits[6:8]))


def read_ofx(
    ledger: Ledger,
    text: str,
    account: Account,
    counter_account: Account,
) -> list[Transaction]:
    """Le transacoes OFX contra a conta e a contrapartida informadas."""
    transactions: list[Transaction] = []
    for block in _STMT_RE.findall(text):
        amount_text = _ofx_tag(block, "TRNAMT")
        posted = _ofx_tag(block, "DTPOSTED")
        if amount_text is None or posted is None:
            continue
        amount = money(_parse_amount(amount_text))
        name = _ofx_tag(block, "NAME") or _ofx_tag(block, "MEMO") or ""
        memo = _ofx_tag(block, "MEMO") or ""
        transactions.append(
            Transaction(
                date=_parse_ofx_date(posted),
                description=name,
                payee=name,
                splits=[Split(account, amount, memo), Split(counter_account, -amount)],
            )
        )
    return transactions


# ------------------------------------------------------------------- conveniencia
def _read_text(path: str | Path) -> str:
    data = Path(path).read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


# --------------------------------------------------------------- deduplicacao
def transaction_signature(transaction: Transaction) -> tuple:
    """Assinatura de um lancamento (data, descricao, beneficiario, partidas).

    O memo e ignorado de proposito: bancos costumam variar sufixos.
    """
    splits = tuple(
        sorted((split.account.id, split.amount.minor_units) for split in transaction.splits)
    )
    return (
        transaction.date.isoformat(),
        (transaction.description or "").strip(),
        (transaction.payee or "").strip(),
        splits,
    )


def partition_new(ledger: Ledger, transactions: list[Transaction]) -> tuple[list[Transaction], int]:
    """Separa lancamentos novos dos que ja existem na base.

    Compara so com o que ja esta gravado (nao dentro do lote): duas
    parcelas identicas no mesmo arquivo entram normalmente, mas reimportar
    o arquivo nao duplica nada. Devolve (novos, ignorados).
    """
    seen = {transaction_signature(existing) for existing in ledger.transactions()}
    new: list[Transaction] = []
    skipped = 0
    for transaction in transactions:
        if transaction_signature(transaction) in seen:
            skipped += 1
        else:
            new.append(transaction)
    return new, skipped


def import_csv_file(ledger: Ledger, path: str | Path) -> list[Transaction]:
    return read_transactions_csv(ledger, _read_text(path))


def import_qif_file(ledger: Ledger, path: str | Path, account: Account) -> list[Transaction]:
    return read_qif(ledger, _read_text(path), account)


def import_ofx_file(
    ledger: Ledger,
    path: str | Path,
    account: Account,
    counter_account: Account,
) -> list[Transaction]:
    return read_ofx(ledger, _read_text(path), account, counter_account)
