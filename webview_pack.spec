# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec do Money 2026 (arquivo unico, janela, sem console).

a = Analysis(
    ["src\\money99\\__main_webview__.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("src\\money99\\web\\templates", "web\\templates"),
        ("src\\money99\\web\\static", "web\\static"),
    ],
    hiddenimports=["webview", "flask", "sqlalchemy", "sqlalchemy.dialects.sqlite"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Money2026",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
