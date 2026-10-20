"""Sanidade do esqueleto: app sobe, SPA responde, API responde."""

from __future__ import annotations


def test_index_serves_spa(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Money 99" in res.data


def test_api_accounts_empty(client):
    res = client.get("/api/accounts")
    assert res.status_code == 200
    assert res.get_json() == []
