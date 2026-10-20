"""Testes de formatação/parsing de dinheiro (centavos, pt-BR)."""

from __future__ import annotations

import pytest

from money99.domain.money import format_brl, parse_brl, parse_iso_date


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0,00", 0),
        ("10,00", 1000),
        ("1.234,56", 123456),
        ("-R$ 1.234,56", -123456),
        ("R$ 0,05", 5),
        ("1000", 100000),
    ],
)
def test_parse_brl(text, expected):
    assert parse_brl(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "1,2,3"])
def test_parse_brl_invalid(text):
    with pytest.raises(ValueError):
        parse_brl(text)


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        (0, "0,00"),
        (5, "0,05"),
        (1000, "10,00"),
        (123456, "1.234,56"),
        (-123456, "-1.234,56"),
        (100000000, "1.000.000,00"),
    ],
)
def test_format_brl(cents, expected):
    assert format_brl(cents) == expected


def test_format_brl_symbol():
    assert format_brl(123456, with_symbol=True) == "R$ 1.234,56"
    assert format_brl(-123456, with_symbol=True) == "-R$ 1.234,56"


def test_parse_iso_date():
    assert parse_iso_date("2026-10-19") == (2026, 10, 19)


@pytest.mark.parametrize("bad", ["19/10/2026", "2026-13-01", "2026-10", "abc"])
def test_parse_iso_date_invalid(bad):
    with pytest.raises(ValueError):
        parse_iso_date(bad)
