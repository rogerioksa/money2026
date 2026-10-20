"""Invariantes de transação (partidas dobradas simplificadas)."""

from __future__ import annotations

import pytest

from money99.domain.transaction import Split, Transaction


def make(**kwargs) -> Transaction:
    defaults = {"date": "2026-10-19", "account_id": 1, "amount": -5000, "category_id": 3}
    defaults.update(kwargs)
    return Transaction(**defaults)


def test_valid_single_category():
    make().validate()


def test_valid_transfer():
    make(category_id=None, transfer_account_id=2, amount=-10000).validate()


def test_valid_splits():
    make(
        category_id=None,
        splits=[Split(category_id=3, amount=-3000), Split(category_id=4, amount=-2000)],
    ).validate()


def test_zero_amount_rejected():
    with pytest.raises(ValueError, match="zero"):
        make(amount=0).validate()


def test_same_account_transfer_rejected():
    with pytest.raises(ValueError, match="mesma conta"):
        make(category_id=None, transfer_account_id=1).validate()


def test_transfer_with_category_rejected():
    with pytest.raises(ValueError, match="transferência"):
        make(transfer_account_id=2).validate()


def test_no_category_no_splits_rejected():
    with pytest.raises(ValueError, match="sem categoria"):
        make(category_id=None).validate()


def test_category_and_splits_rejected():
    with pytest.raises(ValueError, match="não ambos"):
        make(splits=[Split(category_id=4, amount=-5000)]).validate()


def test_splits_sum_mismatch_rejected():
    with pytest.raises(ValueError, match="somam"):
        make(
            category_id=None,
            splits=[Split(category_id=3, amount=-3000), Split(category_id=4, amount=-1000)],
        ).validate()


def test_duplicate_split_category_rejected():
    with pytest.raises(ValueError, match="repetida"):
        make(
            category_id=None,
            splits=[Split(category_id=3, amount=-3000), Split(category_id=3, amount=-2000)],
        ).validate()


def test_non_iso_date_rejected():
    with pytest.raises(ValueError, match="não-ISO"):
        make(date="19/10/2026").validate()
