"""Títulos a pagar/receber (CAR/CAP) — puro domínio."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


class TitleType(str):
    RECEIVABLE = "receivable"
    PAYABLE = "payable"


class TitleStatus(str):
    OPEN = "open"
    PARTIAL = "partial"
    PAID = "paid"
    CANCELLED = "cancelled"


@dataclass
class Title:
    type: str  # receivable | payable
    description: str
    amount: int  # centavos, positivo
    due_date: str  # ISO AAAA-MM-DD
    status: str = TitleStatus.OPEN
    account_id: int | None = None
    category_id: int | None = None
    favorecido: str = ""
    favorecido_id: int | None = None
    notes: str = ""
    paid_date: str = ""
    paid_amount: int = 0
    id: int | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if self.type not in (TitleType.RECEIVABLE, TitleType.PAYABLE):
            raise ValueError("tipo inválido")
        if not self.description.strip():
            raise ValueError("descrição é obrigatória")
        if self.amount <= 0:
            raise ValueError("valor deve ser positivo")
        # valida data
        y, m, d = self.due_date.split("-")
        date(int(y), int(m), int(d))
        if self.status not in (
            TitleStatus.OPEN,
            TitleStatus.PARTIAL,
            TitleStatus.PAID,
            TitleStatus.CANCELLED,
        ):
            raise ValueError("status inválido")
        if self.paid_amount < 0:
            raise ValueError("valor pago não pode ser negativo")