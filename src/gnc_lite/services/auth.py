"""Autenticacao e gestao de usuarios de um livro."""

from __future__ import annotations

from gnc_lite.db.repository import Repository
from gnc_lite.domain.user import Role, User, UserError
from gnc_lite.security import hash_password, verify_password

MIN_PASSWORD_LENGTH = 4


class AuthService:
    """Cria usuarios, autentica e administra papeis de acesso."""

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def user_count(self) -> int:
        return self.repo.user_count()

    def has_users(self) -> bool:
        return self.user_count() > 0

    def create_user(
        self,
        username: str,
        password: str,
        role: Role,
        display_name: str = "",
    ) -> User:
        username = username.strip()
        self._validate(username, password)
        if self.repo.get_user_by_username(username) is not None:
            raise UserError(f"O usuario {username!r} ja existe")
        user = User(
            username=username,
            role=role,
            display_name=display_name.strip(),
            active=True,
            password_hash=hash_password(password),
        )
        return self.repo.add_user(user)

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.repo.get_user_by_username(username.strip())
        if user is None or not user.active:
            return None
        if verify_password(password, user.password_hash):
            return user
        return None

    def list_users(self) -> list[User]:
        return self.repo.list_users()

    def set_password(self, user: User, password: str) -> User:
        if len(password or "") < MIN_PASSWORD_LENGTH:
            raise UserError(f"A senha deve ter ao menos {MIN_PASSWORD_LENGTH} caracteres")
        user.password_hash = hash_password(password)
        return self.repo.update_user(user)

    def set_active(self, user: User, active: bool) -> User:
        user.active = active
        return self.repo.update_user(user)

    def set_role(self, user: User, role: Role) -> User:
        user.role = role
        return self.repo.update_user(user)

    def rename(self, user: User, username: str, display_name: str) -> User:
        username = username.strip()
        if not username:
            raise UserError("Informe o nome de usuario")
        existing = self.repo.get_user_by_username(username)
        if existing is not None and existing.id != user.id:
            raise UserError(f"O usuario {username!r} ja existe")
        user.username = username
        user.display_name = display_name.strip()
        return self.repo.update_user(user)

    @staticmethod
    def _validate(username: str, password: str) -> None:
        if not username:
            raise UserError("Informe o nome de usuario")
        if len(password or "") < MIN_PASSWORD_LENGTH:
            raise UserError(f"A senha deve ter ao menos {MIN_PASSWORD_LENGTH} caracteres")
