"""Conta contabil (plano de contas)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from gnc_lite.domain.errors import CurrencyMismatchError
from gnc_lite.domain.money import DEFAULT_CURRENCY, Money


class AccountType(Enum):
    """Tipos de conta da contabilidade de partidas dobradas."""

    ASSET = "ativo"
    LIABILITY = "passivo"
    EQUITY = "patrimonio"
    INCOME = "receita"
    EXPENSE = "despesa"

    @property
    def is_debit_normal(self) -> bool:
        """Contas que aumentam com debito (ativo e despesa)."""
        return self in (AccountType.ASSET, AccountType.EXPENSE)

    @property
    def normal_sign(self) -> int:
        """Sinal que apresenta o saldo no sentido natural da conta."""
        return 1 if self.is_debit_normal else -1

    @property
    def label(self) -> str:
        return self.value


#: Natureza operacional da conta: conta comum, cartao de credito (fatura e
#: limite) ou cheque especial (limite vinculado a conta bancaria).
ACCOUNT_KIND_NORMAL = "normal"
ACCOUNT_KIND_CARD = "cartao"
ACCOUNT_KIND_OVERDRAFT = "cheque"
ACCOUNT_KINDS = (ACCOUNT_KIND_NORMAL, ACCOUNT_KIND_CARD, ACCOUNT_KIND_OVERDRAFT)

ACCOUNT_KIND_LABELS = {
    ACCOUNT_KIND_NORMAL: "Padrão",
    ACCOUNT_KIND_CARD: "Cartão de crédito",
    ACCOUNT_KIND_OVERDRAFT: "Cheque especial",
}

#: Tipo contabil imposto por natureza especial (cartao e passivo, cheque e ativo).
ACCOUNT_KIND_TYPE = {
    ACCOUNT_KIND_CARD: AccountType.LIABILITY,
    ACCOUNT_KIND_OVERDRAFT: AccountType.ASSET,
}


@dataclass
class Account:
    """Uma conta do plano de contas.

    O saldo bruto (``raw_balance``) soma as partidas com debitos positivos e
    creditos negativos. O saldo natural aplica :attr:`AccountType.normal_sign`.
    """

    code: str
    name: str
    type: AccountType
    currency: str = DEFAULT_CURRENCY
    description: str = ""
    parent: Account | None = None
    placeholder: bool = False
    id: int | None = None
    children: list[Account] = field(default_factory=list)
    kind: str = ACCOUNT_KIND_NORMAL
    credit_limit_minor: int = 0

    def natural_balance(self, raw_balance: Money) -> Money:
        """Converte o saldo bruto para o saldo no sentido natural da conta."""
        if raw_balance.currency != self.currency:
            raise CurrencyMismatchError(
                f"Saldo em {raw_balance.currency} incompativel com a conta em {self.currency}"
            )
        if self.type.normal_sign < 0:
            return -raw_balance
        return raw_balance

    @property
    def is_special(self) -> bool:
        """Conta com tratamento diferencial (cartao ou cheque especial)."""
        return self.kind in (ACCOUNT_KIND_CARD, ACCOUNT_KIND_OVERDRAFT)

    def used_credit_minor(self, raw_minor: int) -> int:
        """Valor utilizado do limite, em centavos (divida atual, nunca negativo)."""
        return max(0, -raw_minor)

    def available_credit_minor(self, raw_minor: int) -> int | None:
        """Limite disponivel em centavos, ou None quando sem limite definido."""
        if self.credit_limit_minor <= 0:
            return None
        return self.credit_limit_minor - self.used_credit_minor(raw_minor)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"
