"""Consulta de dados de empresa pelo CNPJ (BrasilAPI)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

BRASILAPI_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"


class CnpjLookupError(RuntimeError):
    """Falha temporária ao consultar o CNPJ (rede/serviço)."""


def normalize_cnpj(value: str | None) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 14:
        raise ValueError("CNPJ deve ter 14 dígitos")
    return digits


def validate_cnpj(digits: str) -> bool:
    if len(digits) != 14 or len(set(digits)) == 1:
        return False
    weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for size in (12, 13):
        total = sum(
            int(d) * w for d, w in zip(digits[:size], weights[-size:], strict=True)
        )
        check = 11 - (total % 11)
        if check >= 10:
            check = 0
        if int(digits[size]) != check:
            return False
    return True


def infer_activity(cnae: object) -> str:
    """Mapeia o CNAE (divisão) para a atividade do Caderno do MEI."""
    digits = re.sub(r"\D", "", str(cnae or ""))
    if len(digits) < 2:
        return ""
    division = int(digits[:2])
    if 45 <= division <= 47:
        return "comercio"
    if 10 <= division <= 33:
        return "industria"
    return "servicos"


def fetch_cnpj(value: str | None, *, timeout: float = 8.0) -> dict:
    digits = normalize_cnpj(value)
    if not validate_cnpj(digits):
        raise ValueError("CNPJ inválido")

    request = urllib.request.Request(
        BRASILAPI_URL.format(cnpj=digits),
        headers={"Accept": "application/json", "User-Agent": "Money2026"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise CnpjLookupError("CNPJ não encontrado na Receita") from exc
        raise CnpjLookupError(f"Consulta de CNPJ indisponível (HTTP {exc.code})") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CnpjLookupError(
            "Não foi possível consultar o CNPJ. Verifique a conexão com a internet."
        ) from exc
    except json.JSONDecodeError as exc:
        raise CnpjLookupError("Resposta inválida do serviço de CNPJ") from exc

    secondary = []
    for item in data.get("cnaes_secundarios") or []:
        if isinstance(item, dict):
            secondary.append({
                "codigo": str(item.get("codigo") or "").strip(),
                "descricao": str(item.get("descricao") or "").strip(),
            })
        else:
            secondary.append({"codigo": str(item).strip(), "descricao": ""})

    result = {
        "cnpj": digits,
        "legal_name": str(data.get("razao_social") or "").strip(),
        "trade_name": str(data.get("nome_fantasia") or "").strip(),
        "opened_on": str(data.get("data_inicio_atividade") or "").strip(),
        "status": str(data.get("descricao_situacao_cadastral") or "").strip(),
        "city": str(data.get("municipio") or "").strip(),
        "state": str(data.get("uf") or "").strip(),
        "cnae": str(data.get("cnae_fiscal") or "").strip(),
        "cnae_description": str(data.get("cnae_fiscal_descricao") or "").strip(),
        "secondary_cnaes": secondary,
        "activity": infer_activity(data.get("cnae_fiscal")),
    }
    try:
        from money99.services.anexo_xi import check_cnpj_activities

        result["activity_check"] = check_cnpj_activities(result)
    except Exception:  # pragma: no cover - rede indisponível não deve quebrar consulta
        result["activity_check"] = {"ok": False, "error": "verificação indisponível"}
    return result
