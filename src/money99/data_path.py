"""Localização dos dados do usuário (banco, exports).

REGRA: o diretório de dados em runtime é `data/` (ao lado do exe ou do cwd em
desenvolvimento), com fallback para %APPDATA%/Money99. NUNCA usar o nome `DB/`
no gitignore (case-insensitive no Windows casa com o pacote `db/` de código).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Money99"


def _resource_base() -> Path:
    """Pasta base para recursos empacotados (sys._MEIPASS quando congelado)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[return-value]
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    """Diretório gravável para dados do usuário. Cria se não existir."""
    candidates = [
        Path.cwd() / "data",
        _exe_dir() / "data",
        Path(os.environ.get("APPDATA", Path.home())) / APP_NAME,
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate
        except OSError:
            continue
    raise OSError("Nenhum diretório de dados gravável encontrado")


def _exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def db_path() -> Path:
    return data_dir() / "money99.sqlite"


def exports_dir() -> Path:
    path = data_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backups_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def secret_key() -> str:
    """Chave de assinatura da sessão, persistida em data/. Criada se faltar."""
    import secrets

    path = data_dir() / ".secret_key"
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = secrets.token_hex(32)
    path.write_text(value, encoding="utf-8")
    return value
