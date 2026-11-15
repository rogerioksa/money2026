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
        _seed_profiles(engine)
        _seed_categories(engine)


def _seed_profiles(engine: Engine) -> None:
    """Garante ao menos um perfil 'Pessoal'. Atribui linhas órfãs a ele."""
    with engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM profiles")).scalar()
        if not count:
            conn.execute(
                text(
                    "INSERT INTO profiles (name, kind, cnpj, legal_name, trade_name,"
                    " opened_on, annual_limit, activity, active)"
                    " VALUES ('Pessoal', 'personal', '', '', '', '', 0, 'servicos', 1)"
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


def _migrate(engine: Engine) -> None:
    """Adiciona colunas ausentes em bancos antigos. Nunca apaga dados."""
    expected: dict[str, list[tuple[str, str]]] = {
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
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in expected.items():
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
