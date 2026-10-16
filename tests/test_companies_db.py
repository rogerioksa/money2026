"""Banco ao lado do executavel: pasta DB, criacao e migracao do legado."""

from __future__ import annotations

import json
import sys

from gnc_lite.services import companies
from gnc_lite.services.companies import (
    CompanyRegistry,
    create_company,
    data_directory,
    default_companies_path,
    executable_dir,
)


def test_data_directory_uses_db_next_to_cwd(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = data_directory()
    assert target == tmp_path / "DB"
    assert target.is_dir()


def test_executable_dir_frozen(tmp_path, monkeypatch) -> None:
    fake_exe = tmp_path / "app" / "GnuCashLite.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    assert executable_dir() == tmp_path / "app"


def test_create_company_writes_inside_db(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    registry = CompanyRegistry()
    company = create_company(registry, "Loja X", "admin", "1234")
    assert company.db_path.startswith(str(tmp_path / "DB"))
    assert company.db_path.endswith(".sqlite")
    import os

    assert os.path.exists(company.db_path)
    assert (tmp_path / "DB" / "empresas.json").exists()


def test_migrates_legacy_registry(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    legacy_dir = tmp_path / "appdata" / "GnuCashLite"
    legacy_dir.mkdir(parents=True)
    payload = [{"id": "abc", "name": "Antiga", "db_path": str(legacy_dir / "a.sqlite")}]
    (legacy_dir / "empresas.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.chdir(run_dir)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    target = default_companies_path()

    assert target == run_dir / "DB" / "empresas.json"
    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert companies.CompanyRegistry().get("abc") is not None
