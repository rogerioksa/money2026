"""Caminhos de dados compartilhados (exportacoes, abertura para impressao)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gnc_lite.services.companies import data_directory


def exports_dir() -> Path:
    """Pasta de exportacoes de PDF/CSV, criada se necessario."""
    directory = data_directory() / "exports"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def open_for_print(path: str | Path) -> None:
    """Abre o arquivo no visualizador padrao (de onde o usuario imprime)."""
    target = str(path)
    if os.name == "nt":
        os.startfile(target)  # noqa: S606 - abertura local a pedido do usuario
    elif sys.platform == "darwin":
        subprocess.run(["open", target], check=True)
    else:
        subprocess.run(["xdg-open", target], check=True)
