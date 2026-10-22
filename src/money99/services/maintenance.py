"""Backup, restauração e reset do banco de dados local."""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from money99.data_path import backups_dir

BACKUP_PREFIX = "money99-"
BACKUP_SUFFIX = ".sqlite"

_REQUIRED_TABLES = {"users", "profiles", "accounts", "categories", "transactions"}


class MaintenanceError(ValueError):
    """Erro de validação ou execução de manutenção do banco."""


def _db_file(db_path: str | Path) -> Path:
    return Path(db_path).resolve()


def _backup_name(reason: str | None = None) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = f"{BACKUP_PREFIX}{stamp}" + (f"-{reason}" if reason else "")
    candidate = f"{base}{BACKUP_SUFFIX}"
    counter = 2
    while (backups_dir() / candidate).exists():
        candidate = f"{base}-{counter}{BACKUP_SUFFIX}"
        counter += 1
    return candidate


def _describe(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path),
        "size": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def list_backups() -> list[dict]:
    pattern = f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"
    return [_describe(path) for path in sorted(backups_dir().glob(pattern), reverse=True)]


def make_backup(db_path: str | Path, *, reason: str | None = None) -> dict:
    """Copia o banco via API de backup do SQLite (arquivo consistente)."""
    source = _db_file(db_path)
    if not source.is_file():
        raise MaintenanceError("banco de dados não encontrado")
    target = backups_dir() / _backup_name(reason)
    src = sqlite3.connect(str(source))
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        src.close()
    return _describe(target)


def validate_backup(path: str | Path) -> None:
    """Garante que o arquivo é um SQLite íntegro com as tabelas esperadas."""
    file = Path(path)
    try:
        with file.open("rb") as fh:
            header = fh.read(16)
    except OSError as exc:
        raise MaintenanceError("não foi possível ler o arquivo de backup") from exc
    if header != b"SQLite format 3\x00":
        raise MaintenanceError("o arquivo não é um banco SQLite válido")

    conn = sqlite3.connect(f"{file.resolve().as_uri()}?mode=ro", uri=True)
    try:
        check = conn.execute("PRAGMA integrity_check").fetchone()
        if not check or check[0] != "ok":
            raise MaintenanceError("o backup está corrompido (integrity_check falhou)")
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
    finally:
        conn.close()

    missing = sorted(_REQUIRED_TABLES - tables)
    if missing:
        raise MaintenanceError(f"backup inválido: tabelas ausentes ({', '.join(missing)})")


def _replace_database(db_path: str | Path, source: Path, engine) -> None:
    from money99.db.session import init_db

    target = _db_file(db_path)
    temp = target.with_name(target.name + ".restore.tmp")
    shutil.copyfile(source, temp)
    try:
        engine.dispose()
        for suffix in ("-wal", "-shm"):
            Path(str(target) + suffix).unlink(missing_ok=True)
        os.replace(temp, target)
        init_db(engine)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def restore_database(db_path: str | Path, source: str | Path, engine) -> dict:
    """Substitui o banco atual pelo backup informado, com backup de segurança."""
    file = Path(source)
    validate_backup(file)
    safety = None
    try:
        safety = make_backup(db_path, reason="pre-restore")
    except Exception:
        safety = None

    try:
        _replace_database(db_path, file, engine)
    except Exception:
        if safety:
            try:
                _replace_database(db_path, Path(safety["path"]), engine)
            except Exception:
                pass
        raise

    return {"ok": True, "relogin": True, "backup": safety}


def reset_database(db_path: str | Path, engine) -> dict:
    """Apaga o banco e recria a estrutura vazia (mantendo os backups)."""
    from money99.db.session import init_db

    safety = None
    try:
        safety = make_backup(db_path, reason="pre-reset")
    except Exception:
        safety = None

    target = _db_file(db_path)
    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        Path(str(target) + suffix).unlink(missing_ok=True)
    try:
        init_db(engine)
    except Exception:
        if safety:
            try:
                _replace_database(db_path, Path(safety["path"]), engine)
            except Exception:
                pass
        raise
    return {"ok": True, "relogin": True, "backup": safety}
