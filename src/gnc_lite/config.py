"""Configuracao da aplicacao: perfil de uso (Pessoal/MEI) e dados do MEI.

Guardada em um arquivo JSON separado do livro, na pasta de dados do usuario
(ex.: ``%APPDATA%\\GnuCashLite\\config.json`` no Windows).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path

from gnc_lite.db.chart import CHART_BUSINESS, CHART_PERSONAL
from gnc_lite.domain.money import Money

APP_NAME = "GnuCashLite"
CONFIG_FILENAME = "config.json"

DEFAULT_MEI_LIMIT = "81000.00"
MEI_MONTHLY_LIMIT = "6750.00"


class Profile(Enum):
    """Perfil de uso do aplicativo."""

    PERSONAL = "pessoal"
    MEI = "mei"

    @property
    def label(self) -> str:
        return "Uso pessoal" if self is Profile.PERSONAL else "MEI"

    @property
    def is_mei(self) -> bool:
        return self is Profile.MEI


@dataclass
class AppConfig:
    """Preferencias do usuario, com o bloco de dados do MEI."""

    profile: Profile = Profile.PERSONAL
    mei_nome_empresarial: str = ""
    mei_cnpj: str = ""
    mei_atividade: str = ""
    mei_municipio: str = ""
    mei_uf: str = ""
    mei_inicio_atividade: date | None = None
    mei_limite_anual: Money = field(default_factory=lambda: Money.from_decimal(DEFAULT_MEI_LIMIT))

    # ----------------------------------------------------------- serializacao
    def to_dict(self) -> dict:
        return {
            "profile": self.profile.value,
            "mei": {
                "nome_empresarial": self.mei_nome_empresarial,
                "cnpj": self.mei_cnpj,
                "atividade": self.mei_atividade,
                "municipio": self.mei_municipio,
                "uf": self.mei_uf,
                "inicio_atividade": (
                    self.mei_inicio_atividade.isoformat() if self.mei_inicio_atividade else None
                ),
                "limite_anual": f"{self.mei_limite_anual.amount:.2f}",
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> AppConfig:
        mei = data.get("mei") or {}
        inicio = mei.get("inicio_atividade")
        limite = mei.get("limite_anual") or DEFAULT_MEI_LIMIT
        return cls(
            profile=_profile_from_value(data.get("profile")),
            mei_nome_empresarial=mei.get("nome_empresarial", ""),
            mei_cnpj=mei.get("cnpj", ""),
            mei_atividade=mei.get("atividade", ""),
            mei_municipio=mei.get("municipio", ""),
            mei_uf=mei.get("uf", ""),
            mei_inicio_atividade=date.fromisoformat(inicio) if inicio else None,
            mei_limite_anual=Money.from_decimal(limite),
        )


def _profile_from_value(value: object) -> Profile:
    try:
        return Profile(value)
    except ValueError:
        return Profile.PERSONAL


def chart_for_profile(profile: Profile) -> str:
    """Plano de contas do perfil: empresarial para MEI, pessoal caso contrario."""
    return CHART_BUSINESS if profile.is_mei else CHART_PERSONAL


def default_config_path(app_name: str = APP_NAME, filename: str = CONFIG_FILENAME) -> Path:
    """Caminho padrao do arquivo de configuracao, na pasta de dados do usuario."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    directory = base / app_name
    directory.mkdir(parents=True, exist_ok=True)
    return directory / filename


def load_config(path: str | Path | None = None) -> AppConfig:
    """Le a configuracao; devolve os padroes quando o arquivo nao existe."""
    target = Path(path) if path is not None else default_config_path()
    if not target.exists():
        return AppConfig()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppConfig()
    if not isinstance(data, dict):
        return AppConfig()
    return AppConfig.from_dict(data)


def save_config(config: AppConfig, path: str | Path | None = None) -> Path:
    """Grava a configuracao em JSON, criando a pasta quando necessario."""
    target = Path(path) if path is not None else default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(config.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target
