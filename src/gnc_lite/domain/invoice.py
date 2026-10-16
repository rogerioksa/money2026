"""Titulos a receber e a pagar (contas a receber / contas a pagar)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from gnc_lite.domain.account import Account
from gnc_lite.domain.errors import GncLiteError
from gnc_lite.domain.money import Money
from gnc_lite.domain.party import Party


class InvoiceError(GncLiteError):
    """Titulo invalido."""


class InvoiceKind(Enum):
    """Natureza do titulo."""

    RECEIVABLE = "a_receber"
    PAYABLE = "a_pagar"

    @property
    def label(self) -> str:
        return "A receber" if self is InvoiceKind.RECEIVABLE else "A pagar"


class InvoiceStatus(Enum):
    OPEN = "aberto"
    PARTIAL = "parcial"
    SETTLED = "quitado"

    @property
    def label(self) -> str:
        return self.value


@dataclass
class Settlement:
    """Baixa (recebimento ou pagamento) de parte/todo o titulo."""

    date: date
    amount: Money
    transaction_id: int | None = None
    id: int | None = None


@dataclass
class Invoice:
    """Titulo de conta a receber ou a pagar."""

    kind: InvoiceKind
    amount: Money
    issue_date: date
    due_date: date
    party: Party | None = None
    account: Account | None = None
    description: str = ""
    transaction_id: int | None = None
    settlements: list[Settlement] = field(default_factory=list)
    id: int | None = None

    def __post_init__(self) -> None:
        if self.amount.minor_units <= 0:
            raise InvoiceError("O valor do titulo deve ser positivo")
        if self.due_date < self.issue_date:
            raise InvoiceError("A data de vencimento nao pode ser anterior a emissao")

    @property
    def settled_amount(self) -> Money:
        total = Money.zero(self.amount.currency)
        for settlement in self.settlements:
            total = total + settlement.amount
        return total

    @property
    def open_amount(self) -> Money:
        return self.amount - self.settled_amount

    @property
    def status(self) -> InvoiceStatus:
        if self.settled_amount >= self.amount:
            return InvoiceStatus.SETTLED
        if self.settled_amount.is_zero:
            return InvoiceStatus.OPEN
        return InvoiceStatus.PARTIAL

    def is_overdue(self, today: date) -> bool:
        return self.status is not InvoiceStatus.SETTLED and self.due_date < today

    def party_name(self) -> str:
        return self.party.name if self.party is not None else ""
