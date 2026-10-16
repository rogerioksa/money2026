"""Consulta de situacao cadastral via API publica Minha Receita.

Docs: https://docs.minhareceita.org — ``GET https://minhareceita.org/<cnpj>``,
sem autenticacao. Sem SLA: tudo aqui tem timeout curto e o resultado e
armazenado em cache local (sidecar do banco da empresa) para consulta
periodica sem depender de internet.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

API_BASE = "https://minhareceita.org"
REQUEST_TIMEOUT = 12
STALE_AFTER_DAYS = 30


class CnpjError(Exception):
    """CNPJ invalido ou consulta indisponivel."""


def normalize(cnpj: str) -> str:
    """So digitos; valida tamanho e digitos verificadores."""
    digits = "".join(ch for ch in (cnpj or "") if ch.isdigit())
    if len(digits) != 14:
        raise CnpjError("CNPJ deve ter 14 digitos.")
    if len(set(digits)) == 1:
        raise CnpjError("CNPJ invalido.")
    for length in (12, 13):
        total = sum(int(digits[i]) * _weight(i, length) for i in range(length))
        check = 11 - (total % 11)
        if check >= 10:
            check = 0
        if int(digits[length]) != check:
            raise CnpjError("Digito verificador do CNPJ nao confere.")
    return digits


def _weight(index: int, length: int) -> int:
    weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    if length == 13:
        weights = [6, *weights]
    return weights[index]


def lookup(cnpj: str, *, timeout: int = REQUEST_TIMEOUT) -> dict:
    """Consulta a API e devolve o JSON bruto."""
    digits = normalize(cnpj)
    request = urllib.request.Request(
        f"{API_BASE}/{digits}", headers={"User-Agent": "Money26/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise CnpjError(f"Minha Receita respondeu HTTP {response.status}.")
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise CnpjError("CNPJ nao encontrado na Receita Federal.") from exc
        if exc.code == 400:
            raise CnpjError("CNPJ invalido.") from exc
        raise CnpjError(f"Minha Receita indisponivel (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise CnpjError(f"Sem acesso a Minha Receita: {exc.reason}.") from exc
    except TimeoutError as exc:
        raise CnpjError("Tempo esgotado na consulta do CNPJ.") from exc


def summarize(payload: dict) -> dict:
    """Ficha relevante para o MEI a partir do JSON bruto."""
    situacao = str(payload.get("descricao_situacao_cadastral") or "").upper()
    parts = [
        str(payload.get("descricao_tipo_de_logradouro") or ""),
        str(payload.get("logradouro") or ""),
        str(payload.get("numero") or ""),
    ]
    street = " ".join(part for part in parts if part).strip()
    extra = str(payload.get("complemento") or "")
    district = str(payload.get("bairro") or "")
    address = street + (f" - {extra}" if extra else "")
    if district:
        address += f" - {district}"
    phones = [
        phone
        for phone in (
            str(payload.get("ddd_telefone_1") or ""),
            str(payload.get("ddd_telefone_2") or ""),
        )
        if phone
    ]
    return {
        "cnpj": str(payload.get("cnpj") or ""),
        "razao_social": str(payload.get("razao_social") or ""),
        "nome_fantasia": str(payload.get("nome_fantasia") or ""),
        "situacao": situacao or "DESCONHECIDA",
        "ativa": situacao == "ATIVA",
        "data_situacao": str(payload.get("data_situacao_cadastral") or ""),
        "motivo_situacao": str(payload.get("descricao_motivo_situacao_cadastral") or ""),
        "matriz_filial": str(payload.get("descricao_identificador_matriz_filial") or ""),
        "opcao_mei": payload.get("opcao_pelo_mei"),
        "data_opcao_mei": str(payload.get("data_opcao_pelo_mei") or ""),
        "opcao_simples": payload.get("opcao_pelo_simples"),
        "data_opcao_simples": str(payload.get("data_opcao_pelo_simples") or ""),
        "data_inicio_atividade": str(payload.get("data_inicio_atividade") or ""),
        "cnae_codigo": payload.get("cnae_fiscal"),
        "cnae_descricao": str(payload.get("cnae_fiscal_descricao") or ""),
        "cnaes_secundarios": [
            {
                "codigo": item.get("codigo"),
                "descricao": str(item.get("descricao") or ""),
            }
            for item in (payload.get("cnaes_secundarios") or [])
            if isinstance(item, dict)
        ],
        "endereco": address,
        "cep": str(payload.get("cep") or ""),
        "uf": str(payload.get("uf") or ""),
        "municipio": str(payload.get("municipio") or ""),
        "telefones": phones,
        "capital_social": payload.get("capital_social"),
        "porte": str(payload.get("porte") or ""),
        "natureza_juridica": str(payload.get("natureza_juridica") or ""),
        "qsa": [
            {
                "nome": str(item.get("nome_socio") or ""),
                "qualificacao": str(item.get("qualificacao_socio") or ""),
            }
            for item in (payload.get("qsa") or [])
            if isinstance(item, dict)
        ],
    }


def format_cnpj(digits: str) -> str:
    """14 digitos -> XX.XXX.XXX/XXXX-XX."""
    clean = "".join(ch for ch in digits if ch.isdigit())
    if len(clean) != 14:
        return digits
    return f"{clean[0:2]}.{clean[2:5]}.{clean[5:8]}/{clean[8:12]}-{clean[12:14]}"


def cache_path(db_path: str | Path) -> Path:
    return Path(db_path).with_suffix(".cnpj.json")


def load_cache(db_path: str | Path) -> dict | None:
    target = cache_path(db_path)
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def save_cache(db_path: str | Path, cnpj: str, result: dict) -> dict:
    payload = {
        "cnpj": cnpj,
        "checked_at": date.today().isoformat(),
        "result": result,
    }
    target = cache_path(db_path)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def is_stale(cached: dict | None, cnpj: str, today: date | None = None) -> bool:
    """Cache inexistente, de outro CNPJ ou com mais de 30 dias."""
    if not cached or cached.get("cnpj") != "".join(ch for ch in cnpj if ch.isdigit()):
        return True
    try:
        checked = datetime.fromisoformat(str(cached.get("checked_at"))).date()
    except (TypeError, ValueError):
        return True
    today = today or date.today()
    return (today - checked).days >= STALE_AFTER_DAYS
