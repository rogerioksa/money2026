"""Transações e splits — invariantes de partidas dobradas simplificadas.

Convenção de sinal: `amount` é assinado da perspectiva da conta `account_id`.
Saiu da conta = negativo; entrou = positivo. Transferência = uma única linha com
`transfer_account_id` (o saldo da destino recebe `-amount`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from money99.domain.money import parse_iso_date


@dataclass
class Split:
    category_id: int
    amount: int  # centavos, assinado; soma deve igualar o amount da transação


@dataclass
class Transaction:
    date: str  # ISO AAAA-MM-DD
    account_id: int
    amount: int  # centavos, assinado
    description: str = ""
    category_id: int | None = None
    transfer_account_id: int | None = None
    splits: list[Split] = field(default_factory=list)
    notes: str = ""
    reconciled: bool = False
    doc_issued: bool = False  # MEI: venda com documento fiscal (PJ)
    id: int | None = field(default=None, compare=False)

    def validate(self) -> None:
        parse_iso_date(self.date)
        if self.amount == 0:
            raise ValueError("valor zero não é permitido")
        if self.transfer_account_id is not None:
            if self.transfer_account_id == self.account_id:
                raise ValueError("transferência para a mesma conta")
            if self.category_id is not None or self.splits:
                raise ValueError("transferência não pode ter categoria/splits")
            return
        # Transação sem categoria é permitida (pendente de categorização, ex.:
        # importada de extrato). Deve, porém, não misturar splits com categoria.
        if self.category_id is not None and self.splits:
            raise ValueError("use categoria ou splits, não ambos")
        if self.splits:
            if len({s.category_id for s in self.splits}) != len(self.splits):
                raise ValueError("categoria repetida nos splits")
            if sum(s.amount for s in self.splits) != self.amount:
                raise ValueError("splits não somam o valor da transação")
