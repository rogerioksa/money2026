"""Ponto de entrada do Money 26 (Webview)."""

from __future__ import annotations


def main() -> int:
    from gnc_lite.app_webview import run_webview

    run_webview()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
