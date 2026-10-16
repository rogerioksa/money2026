"""Lancamento contabil e suas partidas (splits) - partidas dobradas."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from gnc_lite.domain.account import Account
from gnc_lite.domain.errors import InvalidSplitError, UnbalancedTransactionError
from gnc_lite.domain.money import DEFAULT_CURRENCY, Money


@dataclass
class Split:
    """Uma perna do lancamento: uma conta e um valor com sinal.

    Debitos sao positivos, creditos negativos.
    """

    account: Account
    amount: Money
    memo: str = ""
    id: int | None = None

    def __post_init__(self) -> None:
        if self.account.placeholder:
            raise InvalidSplitError(
                f"Conta {self.account} e apenas agrupadora e nao pode receber partidas"
            )

    def __str__(self) -> str:
        return f"{self.account.code} {self.amount}"


@dataclass
class Transaction:
    """Lancamento balanceado de partidas dobradas.

    Invariante: no minimo 2 partidas, todas na mesma moeda, somando zero.
    """

    date: date
    description: str
    splits: list[Split] = field(default_factory=list)
    currency: str = DEFAULT_CURRENCY
    number: str = ""
    payee: str = ""
    memo: str = ""
    id: int | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if len(self.splits) < 2:
            raise UnbalancedTransactionError(
                "Um lancamento precisa de ao menos duas partidas (debito e credito)"
            )
        total = Money.zero(self.currency)
        for split in self.splits:
            if split.amount.currency != self.currency:
                raise UnbalancedTransactionError(
                    f"Partida em {split.amount.currency} nao bate com o "
                    f"lancamento em {self.currency}"
                )
            total = total + split.amount
        if not total.is_zero:
            raise UnbalancedTransactionError(f"Lancamento nao balanceado: diferenca de {total}")

    def balance(self) -> Money:
        """Soma das partidas (zero quando balanceado)."""
        total = Money.zero(self.currency)
        for split in self.splits:
            total = total + split.amount
        return total

    @property
    def total_debits(self) -> Money:
        return _sum_positive(self.splits, self.currency)

    @property
    def total_credits(self) -> Money:
        return _sum_negative(self.splits, self.currency)

    def accounts(self) -> Iterable[Account]:
        return (split.account for split in self.splits)


def _sum_positive(splits: Iterable[Split], currency: str) -> Money:
    total = Money.zero(currency)
    for split in splits:
        if split.amount.minor_units > 0:
            total = total + split.amount
    return total


def _sum_negative(splits: Iterable[Split], currency: str) -> Money:
    total = Money.zero(currency)
    for split in splits:
        if split.amount.minor_units < 0:
            total = total + split.amount
    return -total
