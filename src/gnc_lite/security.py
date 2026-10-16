"""Hash e verificacao de senhas (PBKDF2-HMAC-SHA256 com salt aleatorio).

Nunca armazenar senha em texto puro. O formato guardado e
``pbkdf2_sha256$<iteracoes>$<salt_hex>$<hash_hex>``.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 200_000
_SALT_BYTES = 16
_KEY_LEN = 32


def hash_password(password: str, *, iterations: int = DEFAULT_ITERATIONS) -> str:
    """Gera o hash da senha no formato encapsulado (com salt)."""
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, _KEY_LEN)
    return f"{ALGORITHM}${iterations}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Confere a senha contra o hash guardado, em tempo constante."""
    try:
        algorithm, iterations_text, salt_hex, expected_hex = encoded.split("$")
    except (AttributeError, ValueError):
        return False
    if algorithm != ALGORITHM:
        return False
    try:
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, _KEY_LEN)
    return hmac.compare_digest(derived.hex(), expected_hex)
