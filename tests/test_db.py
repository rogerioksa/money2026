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


def test_future_transactions_not_in_balance(tmp_path):
    engine, session = setup_db(tmp_path)
    repo = Repository(session)
    checking = repo.add_account(Account(name="Conta", type="bank", initial_balance=50000))
    savings = repo.add_account(Account(name="Poupança", type="bank", initial_balance=0))

    repo.add_transaction(Transaction(
        date="2200-01-01", account_id=checking.id, amount=-7000,
        transfer_account_id=savings.id,
    ))

    balances = repo.account_balances(checking.id)
    assert balances == {"balance": 50000, "future": -7000}
    assert repo.account_balance(checking.id) == 50000
    assert repo.account_future_balance(checking.id) == -7000
    assert repo.account_balances(savings.id) == {"balance": 0, "future": 7000}


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
        indexes = {r[1] for r in conn.execute(text("PRAGMA index_list(transactions)"))}
        assert "ix_transactions_profile_description" in indexes


def test_legacy_migration_adds_credit_limit(tmp_path):
    """Banco antigo (accounts sem 'credit_limit') é migrado sem perder dados."""
    db_file = tmp_path / "legacy2.sqlite"
    engine = connect(db_file)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE accounts ("
            "id INTEGER PRIMARY KEY, name VARCHAR(120), type VARCHAR(20),"
            "initial_balance INTEGER, active BOOLEAN)"
        ))
        conn.execute(text(
            "INSERT INTO accounts (name, type, initial_balance, active)"
            " VALUES ('Banco', 'bank', 1000, 1)"
        ))
    init_db(engine)
    with engine.connect() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(accounts)"))}
        assert "credit_limit" in cols
        row = conn.execute(text("SELECT name, initial_balance FROM accounts")).fetchone()
        assert row == ("Banco", 1000)


def test_account_credit_limit_persist_and_clear(tmp_path):
    engine, session = setup_db(tmp_path)
    repo = Repository(session)
    card = repo.add_account(Account(name="Cartão", type="credit", credit_limit=500000))
    assert repo.get_account(card.id).credit_limit == 500000
    # Limite também é aceito em outros tipos de conta (ex.: limite de cheque especial)
    bank = repo.add_account(Account(name="Banco", type="bank", credit_limit=999))
    assert repo.get_account(bank.id).credit_limit == 999
    # Sem limite informado permanece zerado
    cash = repo.add_account(Account(name="Dinheiro", type="cash"))
    assert repo.get_account(cash.id).credit_limit == 0


def test_migration_backfills_null_credit_limit(tmp_path):
    """Banco cuja coluna credit_limit existe mas com NULL (ADD COLUMN antigo)
    não pode quebrar o carregamento das contas (bug de 500)."""
    db_file = tmp_path / "legacy_null.sqlite"
    engine = connect(db_file)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE accounts ("
            "id INTEGER PRIMARY KEY, name VARCHAR(120), type VARCHAR(20),"
            "initial_balance INTEGER, active BOOLEAN, credit_limit INTEGER)"
        ))
        conn.execute(text(
            "INSERT INTO accounts (name, type, initial_balance, active, credit_limit)"
            " VALUES ('ITAU', 'bank', 3856, 1, NULL)"
        ))
    init_db(engine)
    repo = Repository(make_session(engine))
    accounts = repo.list_accounts()
    assert accounts[0].credit_limit == 0

    with engine.connect() as conn:
        assert conn.execute(text("SELECT credit_limit FROM accounts")).scalar() == 0


def test_migration_adds_mei_columns(tmp_path):
    """Banco antigo (sem profiles.activity e transactions.doc_issued) é migrado
    e recebe backfill, sem perder dados."""
    db_file = tmp_path / "legacy_mei.sqlite"
    engine = connect(db_file)
    init_db(engine)  # schema atual
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE profiles DROP COLUMN activity"))
        conn.execute(text("ALTER TABLE transactions DROP COLUMN doc_issued"))
        conn.execute(text(
            "INSERT INTO profiles (name, kind, cnpj, legal_name, trade_name,"
            " opened_on, annual_limit, active)"
            " VALUES ('Antigo', 'business', '', '', '', '', 8100000, 1)"
        ))
        conn.execute(text(
            "INSERT INTO transactions (profile_id, date, description, account_id,"
            " amount, category_id, transfer_account_id, notes, reconciled)"
            " VALUES (1, '2026-01-15', 'antiga', 1, -999, 1, NULL, '', 0)"
        ))
    init_db(engine)  # roda a migração
    with engine.connect() as conn:
        pcols = {r[1] for r in conn.execute(text("PRAGMA table_info(profiles)"))}
        tcols = {r[1] for r in conn.execute(text("PRAGMA table_info(transactions)"))}
        assert "activity" in pcols
        assert "doc_issued" in tcols
        assert conn.execute(
            text("SELECT activity FROM profiles WHERE name = 'Antigo'")
        ).scalar() == "servicos"
        assert conn.execute(
            text("SELECT doc_issued FROM transactions WHERE description = 'antiga'")
        ).scalar() == 0


def test_legacy_migration_adds_title_cost_center(tmp_path):
    """Banco antigo (titles sem cost_center_id) é migrado sem perder dados."""
    db_file = tmp_path / "legacy_titles.sqlite"
    engine = connect(db_file)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE titles ("
            "id INTEGER PRIMARY KEY, profile_id INTEGER, type VARCHAR(12),"
            "description VARCHAR(240), amount INTEGER, due_date VARCHAR(10),"
            "status VARCHAR(12), account_id INTEGER, category_id INTEGER,"
            "favorecido VARCHAR(160), favorecido_id INTEGER, notes TEXT,"
            "paid_date VARCHAR(10), paid_amount INTEGER)"
        ))
        conn.execute(text(
            "INSERT INTO titles (type, description, amount, due_date, status,"
            " favorecido, notes, paid_date, paid_amount)"
            " VALUES ('payable', 'Energia', 25000, '2026-06-10', 'open',"
            " '', '', '', 0)"
        ))
    init_db(engine)  # roda a migração
    with engine.connect() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(titles)"))}
        assert "cost_center_id" in cols
        row = conn.execute(
            text("SELECT description, amount, cost_center_id FROM titles")
        ).fetchone()
        assert row == ("Energia", 25000, None)
