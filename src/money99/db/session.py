"""Engine, sessão e migração leve de schema (colunas faltantes)."""

from __future__ import annotations

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


def connect(db_path: str | Path) -> Engine:
    return create_engine(f"sqlite:///{db_path}")


def make_session(engine: Engine):
    from sqlalchemy.orm import Session

    return Session(engine)


def init_db(engine: Engine, *, seed: bool = True) -> None:
    Base.metadata.create_all(engine)
    _migrate(engine)
    if seed:
        _seed_categories(engine)


def _seed_categories(engine: Engine) -> None:
    with engine.begin() as conn:
        exists = conn.execute(text("SELECT COUNT(*) FROM categories")).scalar()
        if exists:
            return
        for name, kind in DEFAULT_CATEGORIES:
            conn.execute(
                text("INSERT INTO categories (name, kind, parent_id) VALUES (:n, :k, NULL)"),
                {"n": name, "k": kind},
            )


def _migrate(engine: Engine) -> None:
    """Adiciona colunas ausentes em bancos antigos. Nunca apaga dados."""
    expected: dict[str, list[tuple[str, str]]] = {
        "accounts": [
            ("name", "VARCHAR(120)"),
            ("type", "VARCHAR(20)"),
            ("initial_balance", "INTEGER"),
            ("active", "BOOLEAN"),
        ],
        "categories": [
            ("name", "VARCHAR(120)"),
            ("kind", "VARCHAR(10)"),
            ("parent_id", "INTEGER"),
        ],
        "transactions": [
            ("date", "VARCHAR(10)"),
            ("description", "VARCHAR(240)"),
            ("account_id", "INTEGER"),
            ("amount", "INTEGER"),
            ("category_id", "INTEGER"),
            ("transfer_account_id", "INTEGER"),
            ("notes", "TEXT"),
            ("reconciled", "BOOLEAN"),
        ],
        "splits": [
            ("transaction_id", "INTEGER"),
            ("category_id", "INTEGER"),
            ("amount", "INTEGER"),
        ],
        "budgets": [
            ("year", "INTEGER"),
            ("month", "INTEGER"),
            ("category_id", "INTEGER"),
            ("planned", "INTEGER"),
        ],
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in expected.items():
            if not inspector.has_table(table):
                continue
            existing = {col["name"] for col in inspector.get_columns(table)}
            for col_name, col_type in columns:
                if col_name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
