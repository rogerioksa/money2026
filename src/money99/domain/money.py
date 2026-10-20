"""Dinheiro em unidades menores (centavos). Nunca usar float para valores."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def parse_brl(text: str) -> int:
    """Converte texto pt-BR ('1.234,56', '-R$ 10,00') em centavos (int)."""
    cleaned = text.strip().replace("R$", "").replace(" ", "").replace("\u00a0", "")
    if not cleaned:
        raise ValueError("valor vazio")
    negative = cleaned.startswith("-")
    cleaned = cleaned.lstrip("+-")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"valor inválido: {text!r}") from exc
    cents = int((value * 100).to_integral_value())
    return -cents if negative else cents


def format_brl(cents: int, *, with_symbol: bool = False) -> str:
    """Formata centavos como texto pt-BR ('1.234,56')."""
    negative = cents < 0
    absolute = abs(cents)
    integer = f"{absolute // 100:,}".replace(",", ".")
    result = f"{integer},{absolute % 100:02d}"
    if negative:
        result = f"-{result}"
    if with_symbol:
        body = result.lstrip("-")
        result = f"-R$ {body}" if negative else f"R$ {body}"
    return result


def parse_iso_date(date_str: str) -> tuple[int, int, int]:
    """Valida data ISO AAAA-MM-DD e retorna (ano, mês, dia)."""
    parts = date_str.split("-")
    if len(parts) != 3:
        raise ValueError(f"data não-ISO: {date_str!r}")
    year, month, day = (int(p) for p in parts)
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2200):
        raise ValueError(f"data inválida: {date_str!r}")
    return year, month, day
