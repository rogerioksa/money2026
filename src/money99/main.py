"""Ponto de entrada do Money 99 (janela pywebview)."""

from __future__ import annotations


def main() -> int:
    from money99.app import run_webview

    run_webview()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
