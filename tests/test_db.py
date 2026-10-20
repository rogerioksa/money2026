"""Banco: init, seed, migração legada, repository (CRUD + saldo + filtros)."""

from __future__ import annotations

from sqlalchemy import text

from money99.db.repository import Repository
from money99.db.session import connect, init_db, make_session
from money99.domain.account import Account
from money99.domain.transaction import Split, Transaction


def setup_db(tmp_path):
    engine = connect(tmp_path / "test.sqlite")
    init_db(engine)
    return engine, make_session(engine)


def test_init_seeds_categories(tmp_path):
    engine, session = setup_db(tmp_path)
    repo = Repository(session)
    names = {c.name for c in repo.list_categories()}
    assert "Alimentação" in names
    assert "Salário" in names
    assert len(repo.list_categories()) == 12
    assert {c.kind for c in repo.list_categories()} == {"income", "expense"}


def test_account_crud_and_balance(tmp_path):
    engine, session = setup_db(tmp_path)
    repo = Repository(session)
    account = repo.add_account(Account(name="Banco", type="bank", initial_balance=100000))
    category = repo.list_categories(kind="expense")[0]

    txn = repo.add_transaction(
        Transaction(date="2026-10-01", account_id=account.id, amount=-2500,
                    description="Mercado", category_id=category.id)
    )
    assert repo.account_balance(account.id) == 100000 - 2500

    repo.delete_transaction(txn.id)
    assert repo.account_balance(account.id) == 100000


def test_transfer_moves_balance(tmp_path):
    engine, session = setup_db(tmp_path)
    repo = Repository(session)
    checking = repo.add_account(Account(name="Conta", type="bank", initial_balance=50000))
    savings = repo.add_account(Account(name="Poupança", type="bank", initial_balance=0))

    repo.add_transaction(
        Transaction(date="2026-10-02", account_id=checking.id, amount=-20000,
                    transfer_account_id=savings.id)
    )
    assert repo.account_balance(checking.id) == 30000
    assert repo.account_balance(savings.id) == 20000


def test_delete_account_with_transactions_rejected(tmp_path):
    engine, session = setup_db(tmp_path)
    repo = Repository(session)
    account = repo.add_account(Account(name="Banco", type="bank"))
    category = repo.list_categories(kind="expense")[0]
    repo.add_transaction(
        Transaction(date="2026-10-01", account_id=account.id, amount=-100, category_id=category.id)
    )
    try:
        repo.delete_account(account.id)
        raise AssertionError("deveria ter levantado ValueError")
    except ValueError:
        pass


def test_splits_and_category_filter(tmp_path):
    engine, session = setup_db(tmp_path)
    repo = Repository(session)
    account = repo.add_account(Account(name="Banco", type="bank", initial_balance=0))
    cats = {c.name: c for c in repo.list_categories(kind="expense")}
    food = cats["Alimentação"]
    transport = cats["Transporte"]

    repo.add_transaction(
        Transaction(date="2026-10-05", account_id=account.id, amount=-4500,
                    description="Feira+Uber",
                    splits=[Split(category_id=food.id, amount=-3000),
                            Split(category_id=transport.id, amount=-1500)])
    )
    by_food = repo.list_transactions(category_id=food.id)
    assert len(by_food) == 1
    by_transport = repo.list_transactions(category_id=transport.id)
    assert len(by_transport) == 1
    assert len(repo.list_transactions(category_id=cats["Lazer"].id)) == 0


def test_date_filters(tmp_path):
    engine, session = setup_db(tmp_path)
    repo = Repository(session)
    account = repo.add_account(Account(name="Banco", type="bank"))
    cat = repo.list_categories(kind="expense")[0]
    for day in ("2026-09-30", "2026-10-01", "2026-11-01"):
        repo.add_transaction(
            Transaction(date=day, account_id=account.id, amount=-100, category_id=cat.id)
        )
    oct_only = repo.list_transactions(start="2026-10-01", end="2026-10-31")
    assert [t.date for t in oct_only] == ["2026-10-01"]


def test_budget_upsert(tmp_path):
    engine, session = setup_db(tmp_path)
    repo = Repository(session)
    cat = repo.list_categories(kind="expense")[0]
    repo.set_budget(2026, 10, cat.id, 500000)
    repo.set_budget(2026, 10, cat.id, 550000)
    session.commit()
    rows = repo.list_budget(2026, 10)
    assert len(rows) == 1
    assert rows[0].planned == 550000


def test_legacy_migration_adds_missing_column(tmp_path):
    """Banco antigo (sem coluna 'reconciled') é migrado sem perder dados."""
    db_file = tmp_path / "legacy.sqlite"
    engine = connect(db_file)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE transactions ("
            "id INTEGER PRIMARY KEY, date VARCHAR(10), description VARCHAR(240),"
            "account_id INTEGER, amount INTEGER, category_id INTEGER,"
            "transfer_account_id INTEGER, notes TEXT)"
        ))
        conn.execute(text(
            "INSERT INTO transactions (date, description, account_id, amount,"
            " category_id, notes) VALUES ('2026-01-15', 'antiga', 1, -999, 1, '')"
        ))
    init_db(engine)
    with engine.connect() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(transactions)"))}
        assert "reconciled" in cols
        row = conn.execute(text("SELECT description, amount FROM transactions")).fetchone()
        assert row == ("antiga", -999)
