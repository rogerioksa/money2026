"""Perfis: separação de dados (pessoal x empresarial/MEI). Puro domínio."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

DEFAULT_ANNUAL_LIMIT = 8_100_000  # R$ 81.000,00 (limite anual do MEI)


class ProfileKind(StrEnum):
    PERSONAL = "personal"
    BUSINESS = "business"


class MeiActivity(StrEnum):
    """Atividade principal do MEI (define a página do Caderno do MEI)."""

    COMERCIO = "comercio"
    INDUSTRIA = "industria"
    SERVICOS = "servicos"


@dataclass
class Profile:
    name: str
    kind: ProfileKind = ProfileKind.PERSONAL
    cnpj: str = ""
    legal_name: str = ""
    trade_name: str = ""
    opened_on: str = ""  # ISO AAAA-MM-DD
    annual_limit: int = DEFAULT_ANNUAL_LIMIT  # centavos
    activity: MeiActivity = MeiActivity.SERVICOS
    active: bool = True
    id: int | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("nome do perfil é obrigatório")
        self.kind = ProfileKind(self.kind)
        self.activity = MeiActivity(self.activity or MeiActivity.SERVICOS)
        if self.annual_limit is None:
            self.annual_limit = DEFAULT_ANNUAL_LIMIT
        if self.annual_limit < 0:
            raise ValueError("limite anual não pode ser negativo")
