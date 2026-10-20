"""Conta de domínio."""

from __future__ import annotations

import pytest

from money99.domain.account import Account, AccountType


def test_account_valid():
    account = Account(name="Banco", type="bank", initial_balance=100000)
    assert account.type is AccountType.BANK


def test_account_blank_name_rejected():
    with pytest.raises(ValueError):
        Account(name="  ", type="bank")


def test_account_invalid_type_rejected():
    with pytest.raises(ValueError):
        Account(name="X", type="crypto")
