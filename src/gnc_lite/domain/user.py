"""Usuario do sistema e seu papel de acesso (perfil de permissoes)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from gnc_lite.domain.errors import GncLiteError


class UserError(GncLiteError):
    """Dados de usuario invalidos."""


class Role(Enum):
    """Papel de acesso do usuario."""

    ADMIN = "admin"
    OPERATOR = "operador"
    VIEWER = "consulta"

    @property
    def label(self) -> str:
        return {
            Role.ADMIN: "Administrador",
            Role.OPERATOR: "Operador",
            Role.VIEWER: "Consulta",
        }[self]

    @property
    def is_admin(self) -> bool:
        return self is Role.ADMIN

    @property
    def can_write(self) -> bool:
        """Pode criar/editar lancamentos e titulos."""
        return self in (Role.ADMIN, Role.OPERATOR)


@dataclass
class User:
    """Usuario autenticavel de um livro/empresa."""

    username: str
    role: Role = Role.VIEWER
    display_name: str = ""
    active: bool = True
    password_hash: str = ""
    id: int | None = None

    @property
    def label(self) -> str:
        return self.display_name or self.username
