"""Obrigacoes do MEI: vencimentos, situacoes e registro de cumprimento."""

from __future__ import annotations

from datetime import date

from gnc_lite.config import AppConfig
from gnc_lite.db.repository import Repository
from gnc_lite.db.session import connect, init_db, make_session
from gnc_lite.domain.money import money
from gnc_lite.domain.transaction import Split, Transaction
from gnc_lite.services import obligations
from gnc_lite.services.ledger import Ledger


def _ledger(tmp_path) -> Ledger:
    engine = connect(str(tmp_path / "livro.sqlite"))
    init_db(engine)
    session = make_session(engine)()
    ledger = Ledger(Repository(session))
    ledger.seed_default_chart()
    session.commit()
    return ledger


def _revenue(ledger, when, amount="100.00") -> None:
    caixa = ledger.repo.get_account_by_code("1.1")
    vendas = ledger.repo.get_account_by_code("4.1")
    ledger.post(
        Transaction(
            date=when,
            description="Venda",
            splits=[Split(caixa, money(amount)), Split(vendas, money(f"-{amount}"))],
        )
    )
    ledger.repo.session.commit()


def test_monthly_due_day_20_and_overdue(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    items = obligations.compute_with_records(
        ledger, AppConfig(), 2026, 4, {}, date(2026, 4, 10)
    )
    by_kind = {item.kind: item for item in items}
    assert by_kind["das"].due == date(2026, 4, 20)
    assert by_kind["das"].status == "pendente"
    assert by_kind["rmr"].status == "pendente"

    late = obligations.compute_with_records(
        ledger, AppConfig(), 2026, 4, {}, date(2026, 4, 21)
    )
    assert {i.kind: i.status for i in late}["das"] == "atrasada"


def test_mark_done_and_revenue_detail(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    _revenue(ledger, date(2026, 4, 5), "250.00")
    db_path = str(tmp_path / "livro.sqlite")
    obligations.mark(db_path, "das:2026-04", True)
    items = obligations.compute(
        ledger, AppConfig(), 2026, 4, db_path, date(2026, 4, 25)
    )
    by_kind = {item.kind: item for item in items}
    assert by_kind["das"].status == "concluida"
    assert "250,00" in by_kind["rmr"].detail
    obligations.mark(db_path, "das:2026-04", False)
    assert obligations.load_records(db_path) == {}


def test_dasn_previous_year_and_deadline(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    _revenue(ledger, date(2025, 3, 1), "1000.00")
    items = obligations.compute_with_records(
        ledger, AppConfig(), 2026, 4, {}, date(2026, 4, 10)
    )
    dasn = next(i for i in items if i.kind == "dasn")
    assert dasn.period == "2025"
    assert dasn.due == date(2026, 5, 31)
    assert "1.000,00" in dasn.detail

    late = obligations.compute_with_records(
        ledger, AppConfig(), 2026, 6, {}, date(2026, 6, 1)
    )
    assert next(i for i in late if i.kind == "dasn").status == "atrasada"


def test_cnpj_normalize_and_stale(tmp_path) -> None:
    from gnc_lite.services import cnpj

    assert cnpj.normalize("11.222.333/0001-81") == "11222333000181"
    try:
        cnpj.normalize("11.222.333/0001-82")
        raise AssertionError("deveria falhar")
    except cnpj.CnpjError:
        pass
    db = str(tmp_path / "x.sqlite")
    assert cnpj.is_stale(cnpj.load_cache(db), "11222333000181")
    saved = cnpj.save_cache(db, "11222333000181", {"situacao": "ATIVA"})
    assert not cnpj.is_stale(saved, "11.222.333/0001-81", date.today())
    assert cnpj.is_stale(saved, "11.222.333/0001-81", date(2027, 1, 1))


def test_cnpj_full_summary_and_format() -> None:
    from gnc_lite.services import cnpj

    summary = cnpj.summarize(
        {
            "cnpj": "11222333000181",
            "descricao_situacao_cadastral": "ATIVA",
            "descricao_motivo_situacao_cadastral": "SEM MOTIVO",
            "descricao_identificador_matriz_filial": "MATRIZ",
            "razao_social": "FULANO MEI",
            "nome_fantasia": "FULANO",
            "descricao_tipo_de_logradouro": "RUA",
            "logradouro": "DAS FLORES",
            "numero": "10",
            "complemento": "SALA 1",
            "bairro": "CENTRO",
            "cep": "01001000",
            "uf": "SP",
            "municipio": "SAO PAULO",
            "ddd_telefone_1": "11999998888",
            "cnae_fiscal": 4712100,
            "cnae_fiscal_descricao": "Comércio varejista",
            "cnaes_secundarios": [{"codigo": 1, "descricao": "X"}],
            "capital_social": "1000",
            "porte": "MEI",
            "natureza_juridica": "Empresário Individual",
            "opcao_pelo_simples": True,
            "opcao_pelo_mei": True,
            "data_inicio_atividade": "2020-02-01",
            "qsa": [{"nome_socio": "FULANO", "qualificacao_socio": "Titular"}],
        }
    )
    assert summary["situacao"] == "ATIVA"
    assert summary["endereco"] == "RUA DAS FLORES 10 - SALA 1 - CENTRO"
    assert summary["cnae_descricao"] == "Comércio varejista"
    assert len(summary["cnaes_secundarios"]) == 1
    assert summary["qsa"][0]["nome"] == "FULANO"
    assert cnpj.format_cnpj("11222333000181") == "11.222.333/0001-81"
