"""Clientes e fornecedores."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PartyType(Enum):
    """Tipo de parte relacionada."""

    CUSTOMER = "cliente"
    VENDOR = "fornecedor"

    @property
    def label(self) -> str:
        return self.value


@dataclass
class Party:
    """Cliente ou fornecedor."""

    name: str
    type: PartyType
    document: str = ""
    email: str = ""
    phone: str = ""
    notes: str = ""
    id: int | None = None

    def __str__(self) -> str:
        return self.name
