"""Contas financeiras (puro domínio)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AccountType(StrEnum):
    BANK = "bank"
    CREDIT = "credit"
    CASH = "cash"
    ASSET = "asset"
    INVESTMENT = "investment"


@dataclass
class Account:
    name: str
    type: AccountType
    initial_balance: int = 0  # centavos
    active: bool = True
    credit_limit: int = 0  # centavos; 0 = sem limite informado
    id: int | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("nome da conta é obrigatório")
        self.type = AccountType(self.type)
        if self.credit_limit is None:
            self.credit_limit = 0
        if self.credit_limit < 0:
            raise ValueError("limite de crédito não pode ser negativo")
