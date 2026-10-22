"""Autenticação local: um usuário, senha com hash (PBKDF2-SHA256, stdlib).

Não guarda senha em claro. O hash e o salt ficam na tabela `users`.
A sessão HTTP é assinada pela `SECRET_KEY` do Flask (cookie assinado).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 200_000
_ALGO = "pbkdf2_sha256"


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Retorna (hash, salt). Salt aleatório se não fornecido."""
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS
    )
    return f"{_ALGO}${_ITERATIONS}${digest.hex()}", salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Compara em tempo constante. Formato: '<algo>$<iter>$<hex>'."""
    try:
        algo, iterations, expected = password_hash.split("$")
        if algo != _ALGO:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
        )
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest.hex(), expected)
