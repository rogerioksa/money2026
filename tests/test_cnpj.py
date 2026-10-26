"""Consulta de CNPJ (BrasilAPI): validação e endpoint."""

from __future__ import annotations

import io
import json

import pytest

from money99.services import cnpj as cnpj_service
from money99.services.cnpj import (
    CnpjLookupError,
    fetch_cnpj,
    infer_activity,
    normalize_cnpj,
    validate_cnpj,
)


def test_normalize_cnpj_strips_mask():
    assert normalize_cnpj("11.222.333/0001-81") == "11222333000181"
    assert normalize_cnpj("11222333000181") == "11222333000181"


@pytest.mark.parametrize("value", ["", "123", "1122233300018", "112223330001811"])
def test_normalize_cnpj_rejects_wrong_length(value):
    with pytest.raises(ValueError):
        normalize_cnpj(value)


def test_validate_cnpj():
    assert validate_cnpj("11222333000181")
    assert not validate_cnpj("11222333000182")
    assert not validate_cnpj("00000000000000")


def test_fetch_cnpj_maps_brasilapi_payload(monkeypatch):
    payload = {
        "razao_social": "EMPRESA TESTE LTDA",
        "nome_fantasia": "Teste",
        "data_inicio_atividade": "2020-01-15",
        "descricao_situacao_cadastral": "ATIVA",
        "municipio": "SAO PAULO",
        "uf": "SP",
        "cnae_fiscal": 4711301,
        "cnae_fiscal_descricao": "Comercio varejista",
    }
    body = io.BytesIO(json.dumps(payload).encode("utf-8"))

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()
            return False

    monkeypatch.setattr(
        cnpj_service.urllib.request,
        "urlopen",
        lambda request, timeout: FakeResponse(body.getvalue()),
    )
    monkeypatch.setattr(
        "money99.services.anexo_xi.allowed_cnaes",
        lambda force=False: {"4711301"},
    )
    data = fetch_cnpj("11.222.333/0001-81")
    assert data == {
        "cnpj": "11222333000181",
        "legal_name": "EMPRESA TESTE LTDA",
        "trade_name": "Teste",
        "opened_on": "2020-01-15",
        "status": "ATIVA",
        "city": "SAO PAULO",
        "state": "SP",
        "cnae": "4711301",
        "cnae_description": "Comercio varejista",
        "secondary_cnaes": [],
        "activity": "comercio",
        "activity_check": {
            "ok": True,
            "checked_cnaes": ["4711301"],
            "allowed_cnaes": ["4711301"],
            "disallowed_cnaes": [],
            "all_allowed": True,
            "reference_month": "2026-10",
        },
    }


@pytest.mark.parametrize("cnae, expected", [
    (4711301, "comercio"),
    ("47", "comercio"),
    (1091101, "industria"),
    (4930202, "servicos"),
    ("", ""),
    (None, ""),
])
def test_infer_activity(cnae, expected):
    assert infer_activity(cnae) == expected


def test_fetch_cnpj_network_error(monkeypatch):
    def boom(request, timeout):
        raise OSError("sem rede")

    monkeypatch.setattr(cnpj_service.urllib.request, "urlopen", boom)
    with pytest.raises(CnpjLookupError):
        fetch_cnpj("11222333000181")


def test_api_lookup_cnpj(client, monkeypatch):
    monkeypatch.setattr(
        "money99.api.cnpj_bp.fetch_cnpj",
        lambda value: {
            "cnpj": "11222333000181",
            "legal_name": "EMPRESA TESTE LTDA",
            "trade_name": "Teste",
            "opened_on": "2020-01-15",
            "status": "ATIVA",
            "city": "SAO PAULO",
            "state": "SP",
        },
    )
    res = client.get("/api/cnpj/11222333000181")
    assert res.status_code == 200
    assert res.get_json()["legal_name"] == "EMPRESA TESTE LTDA"


def test_api_lookup_cnpj_invalid(client):
    res = client.get("/api/cnpj/123")
    assert res.status_code == 400
    res = client.get("/api/cnpj/11222333000182")
    assert res.status_code == 400


def test_api_lookup_cnpj_requires_login(anon_client):
    assert anon_client.get("/api/cnpj/11222333000181").status_code == 401


def test_api_lookup_cnpj_upstream_failure(client, monkeypatch):
    def fail(value):
        raise CnpjLookupError("serviço indisponível")

    monkeypatch.setattr("money99.api.cnpj_bp.fetch_cnpj", fail)
    res = client.get("/api/cnpj/11222333000181")
    assert res.status_code == 502
    assert "indisponível" in res.get_json()["error"]
