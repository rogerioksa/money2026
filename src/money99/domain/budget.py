"""Orçamento mensal por categoria (puro domínio)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BudgetEntry:
    year: int
    month: int  # 1-12
    category_id: int
    planned: int  # centavos, positivo

    def __post_init__(self) -> None:
        if not (1 <= self.month <= 12):
            raise ValueError(f"mês inválido: {self.month}")
        if not (2000 <= self.year <= 2200):
            raise ValueError(f"ano inválido: {self.year}")
        if self.planned < 0:
            raise ValueError("valor planejado deve ser positivo")
