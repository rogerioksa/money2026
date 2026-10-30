"""Centro de custo — puro domínio."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CostCenter:
    name: str
    active: bool = True
    id: int | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("nome do centro de custo é obrigatório")