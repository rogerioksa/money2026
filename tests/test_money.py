from decimal import Decimal

import pytest

from gnc_lite.domain.errors import CurrencyMismatchError
from gnc_lite.domain.money import money


def test_from_decimal_arredonda_para_centavos():
    assert money("10.005").minor_units == 1000
    assert money("10.015").minor_units == 1002  # half-even
    assert money(Decimal("0.10")).minor_units == 10


def test_amount_round_trip():
    assert money("10.50").amount == Decimal("10.50")


def test_soma_e_subtracao():
    assert money("10.00") + money("2.50") == money("12.50")
    assert money("10.00") - money("2.50") == money("7.50")
    assert -money("2.50") == money("-2.50")


def test_zeramento():
    total = money("100.00") - money("100.00")
    assert total.is_zero
    assert not total


def test_moedas_incompativeis_levantam_erro():
    with pytest.raises(CurrencyMismatchError):
        money("1.00", "BRL") + money("1.00", "USD")


def test_repr_str():
    assert str(money("10.50")) == "BRL 10.50"
