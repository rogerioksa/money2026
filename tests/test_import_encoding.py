"""Importacao com arquivos fora de UTF-8 (BOM, latin-1 de bancos)."""

from __future__ import annotations

import pytest

from gnc_lite.db.repository import Repository
from gnc_lite.db.session import connect, init_db, make_session
from gnc_lite.services import importer
from gnc_lite.services.importer import ImportParseError
from gnc_lite.services.ledger import Ledger


def _ledger(tmp_path) -> Ledger:
    engine = connect(str(tmp_path / "livro.sqlite"))
    init_db(engine)
    session = make_session(engine)()
    ledger = Ledger(Repository(session))
    ledger.seed_default_chart()
    return ledger


def test_csv_latin1(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    text = (
        "ref,date,account,amount,description\n"
        "1,05/03/2026,1.1,100.00,Venda João\n"
        "1,05/03/2026,4.1,-100.00,Venda João\n"
    )
    path = tmp_path / "extrato.csv"
    path.write_bytes(text.encode("latin-1"))

    transactions = importer.import_csv_file(ledger, path)
    assert len(transactions) == 1
    assert "João" in transactions[0].description


def test_csv_with_bom(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    path = tmp_path / "bom.csv"
    path.write_bytes(
        "\ufeffref,date,account,amount\n1,05/03/2026,1.1,10.00\n1,05/03/2026,4.1,-10.00\n".encode(
            "utf-8"
        )
    )
    transactions = importer.import_csv_file(ledger, path)
    assert len(transactions) == 1


def test_csv_missing_columns_raises(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    path = tmp_path / "ruim.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ImportParseError):
        importer.import_csv_file(ledger, path)


def test_open_for_print_missing_file() -> None:
    from gnc_lite import data_path

    with pytest.raises(OSError):
        data_path.open_for_print("/caminho/que/nao/existe/doc.pdf")


def test_open_for_print_calls_os_opener(tmp_path, monkeypatch) -> None:
    import os

    from gnc_lite import data_path

    target = tmp_path / "doc.pdf"
    target.write_bytes(b"%PDF-1.4 fake")
    called: list[str] = []
    monkeypatch.setattr(
        os, "startfile", lambda path: called.append(path), raising=False
    )
    if os.name == "nt":
        data_path.open_for_print(target)
        assert called == [str(target)]
    else:
        pytest.skip("somente Windows")
