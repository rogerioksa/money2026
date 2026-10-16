from datetime import date

import pytest

from gnc_lite.domain.account import Account, AccountType
from gnc_lite.domain.errors import InvalidSplitError, UnbalancedTransactionError
from gnc_lite.domain.money import money
from gnc_lite.domain.transaction import Split, Transaction


def caixa() -> Account:
    return Account(code="1.1", name="Caixa", type=AccountType.ASSET)


def receita() -> Account:
    return Account(code="4.1", name="Vendas", type=AccountType.INCOME)


def test_lancamento_balanceado():
    tx = Transaction(
        date=date(2026, 1, 1),
        description="Venda em dinheiro",
        splits=[
            Split(caixa(), money("100.00")),
            Split(receita(), money("-100.00")),
        ],
    )
    assert tx.balance().is_zero
    assert tx.total_debits == money("100.00")
    assert tx.total_credits == money("100.00")


def test_lancamento_desbalanceado_levanta_erro():
    with pytest.raises(UnbalancedTransactionError):
        Transaction(
            date=date(2026, 1, 1),
            description="Errado",
            splits=[Split(caixa(), money("100.00")), Split(receita(), money("-90.00"))],
        )


def test_menos_de_duas_partidas_levanta_erro():
    with pytest.raises(UnbalancedTransactionError):
        Transaction(
            date=date(2026, 1, 1),
            description="So uma",
            splits=[Split(caixa(), money("0"))],
        )


def test_conta_placeholder_nao_recebe_partida():
    conta = Account(code="1", name="Ativos", type=AccountType.ASSET, placeholder=True)
    with pytest.raises(InvalidSplitError):
        Split(conta, money("1.00"))


def test_saldo_natural_por_tipo():
    ativo = caixa()
    assert ativo.natural_balance(money("50.00")) == money("50.00")

    passivo = Account(code="2.1", name="Emprestimos", type=AccountType.LIABILITY)
    # saldo bruto negativo (credito) vira positivo no sentido natural
    assert passivo.natural_balance(money("-50.00")) == money("50.00")
