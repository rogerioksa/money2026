"""Registro de empresas (multiempresa): cada empresa aponta para seu livro."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from gnc_lite.db.chart import CHART_BUSINESS
from gnc_lite.domain.user import Role, UserError
from gnc_lite.services.auth import AuthService

APP_NAME = "GnuCashLite"
COMPANIES_FILENAME = "empresas.json"


def executable_dir() -> Path:
    """Pasta do executavel (app congelado) ou pasta atual (desenvolvimento)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def legacy_data_directory(app_name: str = APP_NAME) -> Path:
    """Pasta de dados antiga (%APPDATA%/...); usada so para migracao."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / app_name


def data_directory(app_name: str = APP_NAME) -> Path:
    """Pasta ``DB`` ao lado do executavel (onde ficam os bancos).

    O parametro ``app_name`` e mantido por compatibilidade e ignorado.
    Se nao for possivel criar/gravar ali (ex.: pasta sem permissao),
    cai para a pasta de dados antiga do usuario.
    """
    candidate = executable_dir() / "DB"
    try:
        candidate.mkdir(parents=True, exist_ok=True)
    except OSError:
        return _ensure(legacy_data_directory())
    if not os.access(candidate, os.W_OK):
        return _ensure(legacy_data_directory())
    return candidate


def _ensure(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def default_companies_path() -> Path:
    target = data_directory() / COMPANIES_FILENAME
    if not target.exists():
        legacy = legacy_data_directory() / COMPANIES_FILENAME
        if legacy.exists():
            try:
                shutil.copy2(legacy, target)
            except OSError:
                pass
    return target


@dataclass
class Company:
    """Uma empresa/livro controlado pelo sistema."""

    id: str
    name: str
    db_path: str

    def as_dict(self) -> dict:
        return asdict(self)


class CompanyRegistry:
    """Lista de empresas persistida em JSON, independente dos livros."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_companies_path()
        self._items: list[Company] = self._load()

    def _load(self) -> list[Company]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        result: list[Company] = []
        for item in data if isinstance(data, list) else []:
            try:
                result.append(Company(item["id"], item["name"], item["db_path"]))
            except (KeyError, TypeError):
                continue
        return result

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [company.as_dict() for company in self._items]
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def list(self) -> list[Company]:
        return list(self._items)

    def is_empty(self) -> bool:
        return not self._items

    def get(self, company_id: str) -> Company | None:
        return next((company for company in self._items if company.id == company_id), None)

    def add(self, name: str, db_path: str) -> Company:
        company = Company(id=uuid.uuid4().hex, name=name.strip(), db_path=db_path)
        self._items.append(company)
        self._save()
        return company

    def remove(self, company_id: str) -> None:
        self._items = [company for company in self._items if company.id != company_id]
        self._save()


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", text.strip().lower()).strip("_")
    return cleaned or "empresa"


def create_company(
    registry: CompanyRegistry,
    name: str,
    admin_username: str,
    admin_password: str,
    *,
    db_path: str | Path | None = None,
    chart: str = CHART_BUSINESS,
) -> Company:
    """Cria o banco da empresa, o plano de contas e o usuario administrador."""
    if not name.strip():
        raise UserError("Informe o nome da empresa")
    if db_path is None:
        target = data_directory() / f"{_slug(name)}_{uuid.uuid4().hex[:8]}.sqlite"
    else:
        target = Path(db_path)

    from gnc_lite.db.repository import Repository
    from gnc_lite.db.session import connect, init_db, make_session
    from gnc_lite.services.ledger import Ledger

    engine = connect(target)
    init_db(engine)
    session = make_session(engine)()
    try:
        repo = Repository(session)
        ledger = Ledger(repo)
        ledger.seed_default_chart(chart)
        AuthService(repo).create_user(admin_username, admin_password, Role.ADMIN)
        session.commit()
    finally:
        session.close()

    return registry.add(name, str(target))


def reset_company_db(company: Company) -> None:
    """Zera os dados contabeis, mantendo os usuarios.

    Apaga lancamentos, partidas, titulos, baixas, partes e o plano de contas
    (recriado no padrao empresarial). A tabela de usuarios nao e tocada, de
    modo que logins e senhas continuam validos apos o reset.
    """
    from sqlalchemy import delete

    from gnc_lite.db.models import (
        AccountModel,
        InvoiceModel,
        PartyModel,
        SettlementModel,
        SplitModel,
        TransactionModel,
    )
    from gnc_lite.db.repository import Repository
    from gnc_lite.db.session import connect, init_db, make_session
    from gnc_lite.services.ledger import Ledger

    target = Path(company.db_path)
    engine = connect(target)
    init_db(engine)
    session = make_session(engine)()
    try:
        session.execute(delete(SettlementModel))
        session.execute(delete(InvoiceModel))
        session.execute(delete(SplitModel))
        session.execute(delete(TransactionModel))
        session.execute(delete(PartyModel))
        session.execute(delete(AccountModel))
        session.flush()
        repo = Repository(session)
        Ledger(repo).seed_default_chart(CHART_BUSINESS)
        session.commit()
    finally:
        session.close()
