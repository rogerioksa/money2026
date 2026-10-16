"""Representacao de dinheiro usando inteiros (unidades menores / centavos).

Nunca usar ``float`` para dinheiro. O valor e guardado em unidades menores
(centavos) para evitar erros de arredondamento.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from gnc_lite.domain.errors import CurrencyMismatchError

_QUANT = Decimal("0.01")
_MINOR_FACTOR = 100

DEFAULT_CURRENCY = "BRL"


@dataclass(frozen=True, slots=True)
class Money:
    """Valor monetario imutavel, guardado em unidades menores (centavos)."""

    minor_units: int
    currency: str = DEFAULT_CURRENCY

    @classmethod
    def zero(cls, currency: str = DEFAULT_CURRENCY) -> Money:
        return cls(0, currency)

    @classmethod
    def from_decimal(cls, value: Decimal | int | str, currency: str = DEFAULT_CURRENCY) -> Money:
        """Cria um ``Money`` a partir de um valor decimal, arredondando para centavos."""
        decimal_value = Decimal(str(value)).quantize(_QUANT, rounding=ROUND_HALF_EVEN)
        return cls(int(decimal_value * _MINOR_FACTOR), currency)

    @property
    def amount(self) -> Decimal:
        """Valor em decimal (ex.: ``10.50``)."""
        return (Decimal(self.minor_units) / _MINOR_FACTOR).quantize(_QUANT)

    @property
    def is_zero(self) -> bool:
        return self.minor_units == 0

    def _assert_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Moedas incompativeis: {self.currency!r} e {other.currency!r}"
            )

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._assert_same_currency(other)
        return Money(self.minor_units + other.minor_units, self.currency)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._assert_same_currency(other)
        return Money(self.minor_units - other.minor_units, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.minor_units, self.currency)

    def __abs__(self) -> Money:
        return Money(abs(self.minor_units), self.currency)

    def __bool__(self) -> bool:
        return self.minor_units != 0

    def __lt__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.minor_units < other.minor_units

    def __le__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.minor_units <= other.minor_units

    def __gt__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.minor_units > other.minor_units

    def __ge__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.minor_units >= other.minor_units

    def __str__(self) -> str:
        return f"{self.currency} {self.amount:.2f}"

    __repr__ = __str__


def money(value: Decimal | int | str, currency: str = DEFAULT_CURRENCY) -> Money:
    """Atalho para :meth:`Money.from_decimal`."""
    return Money.from_decimal(value, currency)
