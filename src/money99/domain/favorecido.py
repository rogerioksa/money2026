"""Favorecidos (clientes/fornecedores) — puro domínio."""

from __future__ import annotations

from dataclasses import dataclass, field


class FavorecidoKind(str):
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    BOTH = "both"


@dataclass
class Favorecido:
    name: str
    kind: str = FavorecidoKind.SUPPLIER
    document: str = ""
    phone: str = ""
    email: str = ""
    notes: str = ""
    active: bool = True
    id: int | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("nome do favorecido é obrigatório")
        if self.kind not in (FavorecidoKind.CUSTOMER, FavorecidoKind.SUPPLIER, FavorecidoKind.BOTH):
            raise ValueError("tipo inválido")