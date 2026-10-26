"""Verificação de atividades permitidas ao MEI (Anexo XI da Resolução CGSN).

Baixa o Anexo XI publicado pela Receita Federal, extrai os códigos CNAE
permitidos e permite comparar com os CNAEs cadastrados no CNPJ do perfil.
O cache é renovado automaticamente quando o mês muda (ou sob demanda).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from money99.data_path import data_dir

ANEXO_XI_URL = (
    "https://www8.receita.fazenda.gov.br/SimplesNacional/Arquivos/manual/Anexo_XI.pdf"
)
CNAE_RE = re.compile(r"\d{4}-\d/\d{2}")


class AnexoXiError(RuntimeError):
    """Falha ao baixar/ler o Anexo XI."""


def _cache_path() -> Path:
    return data_dir() / "anexo_xi_cnaes.json"


def _normalize_cnae(value: object) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(7) if digits else ""


def _extract_cnaes(text: str) -> set[str]:
    return {_normalize_cnae(match) for match in CNAE_RE.findall(text)}


def _download_pdf_text() -> str:
    request = urllib.request.Request(
        ANEXO_XI_URL,
        headers={"Accept": "application/pdf", "User-Agent": "Money2026"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AnexoXiError("Não foi possível baixar o Anexo XI.") from exc

    try:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # pragma: no cover - depende do PDF
        raise AnexoXiError("Não foi possível ler o Anexo XI.") from exc


def allowed_cnaes(*, force: bool = False) -> set[str]:
    """Conjunto de CNAEs permitidos ao MEI (cache por mês)."""
    month_key = date.today().strftime("%Y-%m")
    cache_path = _cache_path()
    if not force and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("month") == month_key and cached.get("cnaes"):
                return set(cached["cnaes"])
        except (OSError, json.JSONDecodeError):
            pass

    text = _download_pdf_text()
    cnaes = _extract_cnaes(text)
    if not cnaes:
        raise AnexoXiError("Nenhum CNAE encontrado no Anexo XI.")
    cache_path.write_text(
        json.dumps({"month": month_key, "cnaes": sorted(cnaes)}, ensure_ascii=False),
        encoding="utf-8",
    )
    return cnaes


def check_cnpj_activities(cnpj_data: dict) -> dict:
    """Compara os CNAEs do CNPJ com a lista permitida."""
    try:
        allowed = allowed_cnaes()
    except AnexoXiError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "allowed_cnaes": [],
            "disallowed_cnaes": [],
            "all_allowed": False,
        }

    cnaes: list[str] = []
    primary = _normalize_cnae(cnpj_data.get("cnae"))
    if primary:
        cnaes.append(primary)
    for item in cnpj_data.get("secondary_cnaes", []) or []:
        code = _normalize_cnae(item.get("codigo") if isinstance(item, dict) else item)
        if code and code not in cnaes:
            cnaes.append(code)

    disallowed = [code for code in cnaes if code not in allowed]
    return {
        "ok": True,
        "checked_cnaes": cnaes,
        "allowed_cnaes": [code for code in cnaes if code in allowed],
        "disallowed_cnaes": disallowed,
        "all_allowed": not disallowed,
        "reference_month": date.today().strftime("%Y-%m"),
    }