"""Parsers QIF/OFX e API de importação."""

from __future__ import annotations

import pytest

from money99.services.importer import (
    StatementParseError,
    parse_ofx,
    parse_qif,
    parse_statement,
)

QIF_SAMPLE = """!Type:Bank
D12/31'99
T-50.00
PMERCADO XYZ
MMeat
N123
^
D01/15/2000
T1500.00
PAYMENT
LSalary
^
"""

OFX_SAMPLE = """OFXHEADER:100
DATA:OFXSGML
<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260315120000
<TRNAMT>-42.50
<FITID>ABC123
<NAME>SUPERMERCADO
<MEMO>Compra semanal
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260401
<TRNAMT>2000.00
<FITID>XYZ789
<NAME>SALARIO
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""

PASTE_SAMPLE = """Data Descrição Valor Saldo
Quinta, 22 de outubro de 2026
22/10/2026 Pix enviado-R$ 49,42 R$ 800,62 Caixa Economica Feder
Terça, 20 de outubro de 2026
20/10/2026 Pix enviado-R$ 322,23 R$ 850,04 Elektro Redes S A
20/10/2026 Debito aut. titulo capitalizacao-R$ 50,00 R$ 1.172,27 Iaj60336758
20/10/2026 Pix recebido R$ 1.165,60 R$ 1.222,27 Saulo P. Lima - Me
"""


def test_parse_qif():
    txns = parse_qif(QIF_SAMPLE)
    assert len(txns) == 2
    first = txns[0]
    assert first.date == "1999-12-31"
    assert first.amount == -5000
    assert first.description == "MERCADO XYZ MEAT"
    assert first.memo == ""
    assert first.raw_category.upper() == "SALARY" or txns[1].raw_category.upper() == "SALARY"


def test_parse_qif_iso_dates():
    content = "!Type:Bank\nD2026-03-15\nT-10.00\nPTest\n^\n"
    txns = parse_qif(content)
    assert txns[0].date == "2026-03-15"
    assert txns[0].amount == -1000


def test_parse_ofx():
    txns = parse_ofx(OFX_SAMPLE)
    assert len(txns) == 2
    assert txns[0].date == "2026-03-15"
    assert txns[0].amount == -4250
    assert txns[0].description == "SUPERMERCADO COMPRA SEMANAL"
    assert txns[0].external_id == "ABC123"
    assert txns[1].amount == 200000


def test_parse_statement_detects_format():
    assert len(parse_statement(QIF_SAMPLE, "extrato.qif")) == 2
    assert len(parse_statement(OFX_SAMPLE, "extrato.ofx")) == 2


def test_parse_statement_unknown_format():
    with pytest.raises(StatementParseError):
        parse_statement("isso nao e um extrato", "x.txt")


def test_parse_pasted_bank_text():
    txns = parse_statement(PASTE_SAMPLE, "extrato.txt")
    assert len(txns) == 4
    assert txns[0].date == "2026-10-22"
    assert txns[0].amount == -4942
    assert txns[0].description == "PIX ENVIADO CAIXA ECONOMICA FEDER"
    assert txns[0].memo == ""
    assert txns[3].amount == 116560
    assert txns[3].description == "PIX RECEBIDO SAULO P. LIMA - ME"


def test_parse_ofx_ignores_incomplete_blocks():
    content = "<OFX><STMTTRN><NAME>sem data</NAME></STMTTRN></OFX>"
    assert parse_ofx(content) == []


def test_preview_endpoint(client):
    res = client.post("/api/import/preview", json={"content": QIF_SAMPLE, "filename": "e.qif"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["count"] == 2
    assert body["transactions"][0]["amount"] == -5000

    res = client.post("/api/import/preview", json={"content": "xyz", "filename": "x.txt"})
    assert res.status_code == 400


def test_commit_endpoint_dedup(client):
    account = client.post("/api/accounts", json={"name": "Banco", "type": "bank"}).get_json()
    txns = [
        {"date": "2026-03-15", "amount": -4250, "description": "SUPERMERCADO"},
        {"date": "2026-03-16", "amount": -1000, "description": "PADARIA"},
    ]
    res = client.post("/api/import/commit", json={
        "account_id": account["id"], "transactions": txns,
    })
    assert res.status_code == 200
    assert res.get_json() == {"imported": 2, "skipped": 0}

    # Reimportar o mesmo arquivo não duplica
    res = client.post("/api/import/commit", json={
        "account_id": account["id"], "transactions": txns,
    })
    assert res.get_json() == {"imported": 0, "skipped": 2}

    # Importadas sem categoria (categorização é feita no extrato)
    imported = client.get("/api/transactions").get_json()
    assert len(imported) == 2
    assert all(t["category_id"] is None for t in imported)


def test_commit_validation(client):
    assert client.post("/api/import/commit", json={"transactions": []}).status_code == 400
    account = client.post("/api/accounts", json={"name": "B", "type": "bank"}).get_json()
    # importar sem categoria é permitido
    assert client.post("/api/import/commit", json={
        "account_id": account["id"], "transactions": [{"date": "2026-01-01", "amount": -1}],
    }).status_code == 200
    assert client.post("/api/import/commit", json={
        "account_id": 999, "transactions": [{"date": "2026-01-01", "amount": -1}],
    }).status_code == 404
