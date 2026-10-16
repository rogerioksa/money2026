"""Excecoes do dominio contabil."""

from __future__ import annotations


class GncLiteError(Exception):
    """Erro base do dominio."""


class CurrencyMismatchError(GncLiteError):
    """Operacao entre moedas diferentes."""


class InvalidSplitError(GncLiteError):
    """Partida (split) invalida."""


class UnbalancedTransactionError(GncLiteError):
    """Lancamento nao balanceado (soma das partidas != 0)."""


class ClosedPeriodError(GncLiteError):
    """Operacao em periodo contabil fechado."""
