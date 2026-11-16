"""Engine, sessão, migração leve e preparação segura do banco."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text

from money99.db.models import Base

DEFAULT_CATEGORIES = [
    ("Salário", "income"),
    ("Outras receitas", "income"),
    ("Moradia", "expense"),
    ("Alimentação", "expense"),
    ("Transporte", "expense"),
    ("Saúde", "expense"),
    ("Educação", "expense"),
    ("Lazer", "expense"),
    ("Compras", "expense"),
    ("Impostos e taxas", "expense"),
    ("Investimentos", "expense"),
    ("Outras despesas", "expense"),
]

# Versão lógica do schema. Incrementar quando houver migração que exija backup
# mesmo sem colunas novas (ex.: backfill de dados).
SCHEMA_VERSION = 2
BACKUP_PREFIX = "money99-"

_EXPECTED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "profiles": [
        ("name", "VARCHAR(120)"),
        ("kind", "VARCHAR(20)"),
        ("cnpj", "VARCHAR(20)"),
        ("legal_name", "VARCHAR(200)"),
        ("trade_name", "VARCHAR(200)"),
        ("opened_on", "VARCHAR(10)"),
        ("annual_limit", "INTEGER"),
        ("activity", "VARCHAR(20)"),
        ("active", "BOOLEAN"),
    ],
    "accounts": [
        ("profile_id", "INTEGER"),
        ("name", "VARCHAR(120)"),
        ("type", "VARCHAR(20)"),
        ("initial_balance", "INTEGER"),
        ("active", "BOOLEAN"),
        ("credit_limit", "INTEGER"),
    ],
    "categories": [
        ("profile_id", "INTEGER"),
        ("name", "VARCHAR(120)"),
        ("kind", "VARCHAR(10)"),
        ("parent_id", "INTEGER"),
    ],
    "transactions": [
        ("profile_id", "INTEGER"),
        ("date", "VARCHAR(10)"),
        ("description", "VARCHAR(240)"),
        ("account_id", "INTEGER"),
        ("amount", "INTEGER"),
        ("category_id", "INTEGER"),
        ("transfer_account_id", "INTEGER"),
        ("notes", "TEXT"),
        ("reconciled", "BOOLEAN"),
        ("doc_issued", "BOOLEAN"),
        ("cost_center_id", "INTEGER"),
    ],
    "splits": [
        ("transaction_id", "INTEGER"),
        ("category_id", "INTEGER"),
        ("amount", "INTEGER"),
        ("cost_center_id", "INTEGER"),
    ],
    "budgets": [
        ("profile_id", "INTEGER"),
        ("year", "INTEGER"),
        ("month", "INTEGER"),
        ("category_id", "INTEGER"),
        ("planned", "INTEGER"),
    ],
    "titles": [
        ("profile_id", "INTEGER"),
        ("type", "VARCHAR(12)"),
        ("description", "VARCHAR(240)"),
        ("amount", "INTEGER"),
        ("due_date", "VARCHAR(10)"),
        ("status", "VARCHAR(12)"),
        ("account_id", "INTEGER"),
        ("category_id", "INTEGER"),
        ("cost_center_id", "INTEGER"),
        ("favorecido", "VARCHAR(160)"),
        ("favorecido_id", "INTEGER"),
        ("notes", "TEXT"),
        ("paid_date", "VARCHAR(10)"),
        ("paid_amount", "INTEGER"),
    ],
    "favorecidos": [
        ("profile_id", "INTEGER"),
        ("name", "VARCHAR(160)"),
        ("kind", "VARCHAR(12)"),
        ("document", "VARCHAR(20)"),
        ("phone", "VARCHAR(40)"),
        ("email", "VARCHAR(160)"),
        ("notes", "TEXT"),
        ("active", "BOOLEAN"),
    ],
    "cost_centers": [
        ("profile_id", "INTEGER"),
        ("name", "VARCHAR(120)"),
        ("active", "BOOLEAN"),
    ],
    "annual_budgets": [
        ("profile_id", "INTEGER"),
        ("year", "INTEGER"),
        ("category_id", "INTEGER"),
        ("annual_planned", "INTEGER"),
    ],
    "users": [
        ("username", "VARCHAR(120)"),
        ("password_hash", "VARCHAR(255)"),
        ("salt", "VARCHAR(64)"),
    ],
}


def connect(db_path: str | Path) -> Engine:
    return create_engine(f"sqlite:///{db_path}")


def make_session(engine: Engine):
    from sqlalchemy.orm import Session

    return Session(engine)


def init_db(engine: Engine, *, seed: bool = True) -> None:
    Base.metadata.create_all(engine)
    _migrate(engine)
    if seed:
        _seed_profiles(engine)
        _seed_categories(engine)
    with engine.begin() as conn:
        _uppercase_text_columns(conn, inspect(conn))
    _set_schema_version(engine)


def prepare_database(
    engine: Engine,
    *,
    backup_dir: Path | None = None,
    backup_prefix: str = BACKUP_PREFIX,
) -> Path | None:
    """Verifica integridade/versão, faz backup e aplica as migrações.

    O backup (`...-pre-migration.sqlite`) só é criado quando o schema precisa
    mudar ou quando o banco vem de uma versão anterior. Bancos novos não geram
    backup. Retorna o caminho do backup criado ou `None`.
    """
    db_path = _database_path(engine)
    backup: Path | None = None
    if db_path is not None and db_path.exists() and db_path.stat().st_size > 0:
        version = _read_user_version(db_path)
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"banco criado por uma versão mais nova do Money 2026 "
                f"(schema {version} > {SCHEMA_VERSION}): {db_path}"
            )
        if version < SCHEMA_VERSION or _pending_changes(engine):
            target_dir = backup_dir or (db_path.parent / "backups")
            backup = _backup_database(db_path, target_dir, backup_prefix)
    init_db(engine)
    return backup


def _database_path(engine: Engine) -> Path | None:
    database = engine.url.database
    if not database or database == ":memory:" or database.startswith("file:"):
        return None
    return Path(database)


def _read_user_version(db_path: Path) -> int:
    """Valida o arquivo e retorna `PRAGMA user_version` (0 em bancos antigos)."""
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            check = conn.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                detail = check[0] if check else "sem resultado"
                raise RuntimeError(
                    f"banco SQLite corrompido: {db_path} (integrity_check: {detail})"
                )
            version = conn.execute("PRAGMA user_version").fetchone()
    except sqlite3.DatabaseError as exc:
        raise RuntimeError(f"banco SQLite inválido ou corrompido: {db_path}") from exc
    return int(version[0]) if version else 0


def _pending_changes(engine: Engine) -> list[str]:
    """Lista tabelas/colunas ausentes em relação ao schema atual."""
    inspector = inspect(engine)
    pending: list[str] = []
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            pending.append(table.name)
            continue
        existing = {col["name"] for col in inspector.get_columns(table.name)}
        for column, _ in _EXPECTED_COLUMNS.get(table.name, []):
            if column not in existing:
                pending.append(f"{table.name}.{column}")
    return pending


def _backup_database(db_path: Path, backup_dir: Path, prefix: str) -> Path:
    """Copia o banco via API de backup do SQLite antes de migrar."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = f"{prefix}{stamp}-pre-migration"
    target = backup_dir / f"{base}.sqlite"
    counter = 2
    while target.exists():
        target = backup_dir / f"{base}-{counter}.sqlite"
        counter += 1
    try:
        with closing(sqlite3.connect(db_path)) as source, closing(
            sqlite3.connect(target)
        ) as destination:
            source.backup(destination)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


def _set_schema_version(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"PRAGMA user_version = {SCHEMA_VERSION}"))


def _seed_profiles(engine: Engine) -> None:
    """Garante ao menos um perfil 'Pessoal'. Atribui linhas órfãs a ele."""
    with engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM profiles")).scalar()
        if not count:
            conn.execute(
                text(
                    "INSERT INTO profiles (name, kind, cnpj, legal_name, trade_name,"
                    " opened_on, annual_limit, activity, active)"
                    " VALUES ('PESSOAL', 'personal', '', '', '', '', 0, 'servicos', 1)"
                )
            )
        default_id = conn.execute(text("SELECT MIN(id) FROM profiles")).scalar()
        tables = (
            "accounts", "categories", "transactions", "budgets",
            "titles", "favorecidos", "cost_centers", "annual_budgets",
        )
        for table in tables:
            conn.execute(
                text(f"UPDATE {table} SET profile_id = :p WHERE profile_id IS NULL"),
                {"p": default_id},
            )


def _seed_categories(engine: Engine) -> None:
    with engine.begin() as conn:
        for profile_id in conn.execute(text("SELECT id FROM profiles")).scalars():
            exists = conn.execute(
                text("SELECT COUNT(*) FROM categories WHERE profile_id = :p"),
                {"p": profile_id},
            ).scalar()
            if exists:
                continue
            for name, kind in DEFAULT_CATEGORIES:
                conn.execute(
                    text(
                        "INSERT INTO categories (profile_id, name, kind, parent_id)"
                        " VALUES (:p, :n, :k, NULL)"
                    ),
                    {"p": profile_id, "n": name, "k": kind},
                )


# Campos textuais de conteúdo do usuário (exclui códigos/enums/datas usados pela lógica).
_UPPERCASE_COLUMNS: dict[str, tuple[str, ...]] = {
    "profiles": ("name", "cnpj", "legal_name", "trade_name"),
    "accounts": ("name",),
    "categories": ("name",),
    "transactions": ("description", "notes"),
    "titles": ("description", "favorecido", "notes"),
    "favorecidos": ("name", "document", "phone", "email", "notes"),
    "cost_centers": ("name",),
    "users": ("username",),
}


def _upper_text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    return value.upper()


def _uppercase_text_columns(conn, inspector) -> None:
    """Normaliza campos de texto para maiúsculas (idempotente, Unicode)."""
    for table, columns in _UPPERCASE_COLUMNS.items():
        if not inspector.has_table(table):
            continue
        existing = {col["name"] for col in inspector.get_columns(table)}
        cols = [c for c in columns if c in existing]
        if not cols:
            continue
        rows = conn.execute(
            text(f"SELECT rowid AS _rowid, {', '.join(cols)} FROM {table}")
        ).fetchall()
        for row in rows:
            mapping = row._mapping
            updates = {}
            for col in cols:
                current = mapping[col]
                if current is None:
                    continue
                upper = _upper_text(current)
                if upper != current:
                    updates[col] = upper
            if updates:
                set_clause = ", ".join(f"{col} = :{col}" for col in updates)
                updates["_rowid"] = mapping["_rowid"]
                conn.execute(
                    text(f"UPDATE {table} SET {set_clause} WHERE rowid = :_rowid"),
                    updates,
                )


def _migrate(engine: Engine) -> None:
    """Adiciona colunas ausentes em bancos antigos. Nunca apaga dados."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in _EXPECTED_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {col["name"] for col in inspector.get_columns(table)}
            for col_name, col_type in columns:
                if col_name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
        # Backfill de nulos em colunas numéricas recém-adicionadas (ADD COLUMN
        # não aplica DEFAULT a linhas já existentes no SQLite).
        if inspector.has_table("accounts"):
            conn.execute(text(
                "UPDATE accounts SET credit_limit = 0 WHERE credit_limit IS NULL"
            ))
            conn.execute(text(
                "UPDATE accounts SET initial_balance = 0 WHERE initial_balance IS NULL"
            ))
        if inspector.has_table("profiles"):
            conn.execute(text(
                "UPDATE profiles SET activity = 'servicos' WHERE activity IS NULL"
            ))
            conn.execute(text(
                "UPDATE profiles SET annual_limit = 8100000 WHERE annual_limit IS NULL"
            ))
        if inspector.has_table("transactions"):
            conn.execute(text(
                "UPDATE transactions SET doc_issued = 0 WHERE doc_issued IS NULL"
            ))
            conn.execute(text(
                "UPDATE transactions SET amount = 0 WHERE amount IS NULL"
            ))
            # Índice de apoio ao autocomplete de descrições do extrato.
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_transactions_profile_description"
                " ON transactions (profile_id, description)"
            ))
        if inspector.has_table("budgets"):
            conn.execute(text(
                "UPDATE budgets SET planned = 0 WHERE planned IS NULL"
            ))
        if inspector.has_table("titles"):
            conn.execute(text(
                "UPDATE titles SET amount = 0 WHERE amount IS NULL"
            ))
            conn.execute(text(
                "UPDATE titles SET paid_amount = 0 WHERE paid_amount IS NULL"
            ))
        if inspector.has_table("annual_budgets"):
            conn.execute(text(
                "UPDATE annual_budgets SET annual_planned = 0 WHERE annual_planned IS NULL"
            ))
        inspector = inspect(conn)
        _uppercase_text_columns(conn, inspector)
