from datetime import date

from gnc_lite.domain.account import AccountType
from gnc_lite.domain.money import money
from gnc_lite.domain.transaction import Split, Transaction


def test_seed_cria_plano_de_contas_com_hierarquia(ledger):
    accounts = ledger.seed_default_chart()
    assert len(accounts) == 24

    caixa = ledger.repo.get_account_by_code("1.1")
    assert caixa is not None
    assert caixa.type is AccountType.ASSET
    assert caixa.parent is not None
    assert caixa.parent.code == "1"

    conta = ledger.repo.get_account_by_code("1.2.1")
    assert conta is not None
    assert conta.parent is not None
    assert conta.parent.code == "1.2"
    assert conta.parent.parent is not None
    assert conta.parent.parent.code == "1"


def test_list_accounts_liga_pais_e_filhos(ledger):
    ledger.seed_default_chart()
    accounts = ledger.list_accounts()
    ativo = next(a for a in accounts if a.code == "1")
    child_codes = {c.code for c in ativo.children}
    assert {"1.1", "1.2", "1.3"} <= child_codes


def test_persistir_e_recuperar_conta(ledger):
    account = ledger.create_account("9.1", "Conta Teste", AccountType.ASSET)
    assert account.id is not None
    found = ledger.repo.get_account(account.id)
    assert found is not None
    assert found.code == "9.1"
    assert found.name == "Conta Teste"


def test_lancamento_balanceado_persiste_e_calcula_saldo(ledger):
    ledger.seed_default_chart()
    caixa = ledger.repo.get_account_by_code("1.1")
    vendas = ledger.repo.get_account_by_code("4.1")

    tx = Transaction(
        date=date(2026, 1, 10),
        description="Venda a vista",
        splits=[Split(caixa, money("150.00")), Split(vendas, money("-150.00"))],
    )
    ledger.post(tx)
    assert tx.id is not None

    assert ledger.raw_balance(caixa) == money("150.00")
    assert ledger.balance(vendas) == money("150.00")


def test_saldo_de_conta_agrupadora_soma_filhos(ledger):
    ledger.seed_default_chart()
    caixa = ledger.repo.get_account_by_code("1.1")
    banco = ledger.repo.get_account_by_code("1.2.1")
    ativo = ledger.repo.get_account_by_code("1")
    receita = ledger.repo.get_account_by_code("4.1")

    ledger.post(
        Transaction(
            date=date(2026, 2, 1),
            description="Aporte em dinheiro",
            splits=[Split(caixa, money("100.00")), Split(receita, money("-100.00"))],
        )
    )
    ledger.post(
        Transaction(
            date=date(2026, 2, 2),
            description="Deposito em banco",
            splits=[Split(banco, money("60.00")), Split(receita, money("-60.00"))],
        )
    )

    assert ledger.raw_balance(ativo) == money("160.00")


def test_list_transactions_recupera_splits(ledger):
    ledger.seed_default_chart()
    caixa = ledger.repo.get_account_by_code("1.1")
    vendas = ledger.repo.get_account_by_code("4.1")
    ledger.post(
        Transaction(
            date=date(2026, 3, 1),
            description="Venda",
            splits=[Split(caixa, money("25.00")), Split(vendas, money("-25.00"))],
        )
    )
    txs = ledger.transactions()
    assert len(txs) == 1
    assert txs[0].balance().is_zero
    assert {s.account.code for s in txs[0].splits} == {"1.1", "4.1"}


def test_migrate_legacy_accounts_without_kind(tmp_path):
    """Bancos antigos ganham kind/limite com padroes sem perder dados."""
    import sqlite3

    from gnc_lite.db.repository import Repository
    from gnc_lite.db.session import connect, init_db, make_session

    target = tmp_path / "antigo.sqlite"
    connection = sqlite3.connect(target)
    connection.execute(
        "CREATE TABLE accounts (id INTEGER PRIMARY KEY, code VARCHAR(32),"
        " name VARCHAR(128), type VARCHAR(16), currency VARCHAR(3),"
        " description VARCHAR(255), placeholder BOOLEAN, parent_id INTEGER)"
    )
    connection.execute(
        "INSERT INTO accounts (code, name, type) VALUES ('1.1', 'Caixa', 'ativo')"
    )
    connection.commit()
    connection.close()

    engine = connect(target)
    init_db(engine)
    session = make_session(engine)()
    account = Repository(session).get_account_by_code("1.1")
    assert account is not None
    assert account.kind == "normal"
    assert account.credit_limit_minor == 0
    session.close()
