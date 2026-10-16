"""Perfis de plano de contas: pessoal (simplificado) e empresa (completo)."""

from __future__ import annotations

import pytest

from gnc_lite.config import Profile, chart_for_profile
from gnc_lite.db.chart import (
    BUSINESS_CHART,
    CHART_BUSINESS,
    CHART_PERSONAL,
    DEFAULT_CHART,
    PERSONAL_CHART,
    seed_default_chart,
)
from gnc_lite.db.repository import Repository
from gnc_lite.db.session import connect, init_db, make_session
from gnc_lite.domain.account import AccountType
from gnc_lite.services.companies import CompanyRegistry, create_company


def _ledger(tmp_path, name="livro.sqlite"):
    engine = connect(str(tmp_path / name))
    init_db(engine)
    session = make_session(engine)()
    return Repository(session)


def test_business_chart_is_the_default() -> None:
    assert BUSINESS_CHART == DEFAULT_CHART
    assert chart_for_profile(Profile.MEI) == CHART_BUSINESS
    assert chart_for_profile(Profile.PERSONAL) == CHART_PERSONAL


def test_personal_chart_structure(tmp_path) -> None:
    repo = _ledger(tmp_path)
    seed_default_chart(repo, CHART_PERSONAL)

    by_code = {account.code: account for account in repo.list_accounts()}
    assert by_code["4.1"].name == "Salarios"
    assert by_code["4.1"].type is AccountType.INCOME
    assert by_code["5.1"].name == "Moradia"
    assert by_code["3.1"].name == "Patrimonio Inicial"
    assert "1.5" not in by_code  # sem Imobilizado no pessoal
    assert "4.3" not in by_code

    caixa = by_code["1.1"]
    corrente = by_code["1.2.1"]
    assert not caixa.placeholder and caixa.type is AccountType.ASSET
    assert not corrente.placeholder and corrente.type is AccountType.ASSET
    assert corrente.parent is not None and corrente.parent.code == "1.2"
    assert by_code["1"].placeholder


def test_business_chart_keeps_company_codes(tmp_path) -> None:
    repo = _ledger(tmp_path)
    seed_default_chart(repo)

    by_code = {account.code: account for account in repo.list_accounts()}
    assert by_code["4.1"].name == "Vendas"
    assert by_code["4.2"].name == "Servicos"
    assert by_code["3.1"].name == "Capital Social"


def test_unknown_chart_raises(tmp_path) -> None:
    repo = _ledger(tmp_path)
    with pytest.raises(ValueError):
        seed_default_chart(repo, "inexistente")


def test_create_company_with_personal_chart(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    registry = CompanyRegistry()
    company = create_company(registry, "Casa", "admin", "1234", chart=CHART_PERSONAL)

    from gnc_lite.app_webview import open_ledger

    ledger, _session = open_ledger(company.db_path)
    try:
        assert ledger.repo.get_account_by_code("4.1").name == "Salarios"
    finally:
        _session.close()


def test_create_company_defaults_to_business_chart(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    registry = CompanyRegistry()
    company = create_company(registry, "Loja", "admin", "1234")

    from gnc_lite.app_webview import open_ledger

    ledger, _session = open_ledger(company.db_path)
    try:
        assert ledger.repo.get_account_by_code("4.1").name == "Vendas"
    finally:
        _session.close()


def test_personal_chart_keeps_structural_contract() -> None:
    """Contratos usados pelas telas: raiz 1, caixa 1.1/1.2.x, receitas 4.x."""
    personal_codes = {entry.code for entry in PERSONAL_CHART}
    assert {"1", "1.1", "1.2", "1.2.1", "2", "2.1", "3", "4", "5"} <= personal_codes
    assert any(code.startswith("4.") for code in personal_codes)
    assert any(code.startswith("5.") for code in personal_codes)
    # Empresarial tem contas que o pessoal nao tem.
    assert {"1.4", "1.5", "2.2", "2.3", "4.3"}.isdisjoint(personal_codes)
