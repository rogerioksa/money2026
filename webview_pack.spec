# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

block_cipher = None

project_root = Path(sys.argv[0]).parent if False else Path('.')
src = project_root / 'src' / 'gnc_lite'

a = Analysis(
    ['src/gnc_lite/__main_webview__.py'],
    pathex=[str(project_root / 'src')],
    binaries=[],
    datas=[
        (str(src / 'web' / 'templates'), 'gnc_lite/web/templates'),
        (str(src / 'web' / 'static'), 'gnc_lite/web/static'),
    ],
    hiddenimports=[
        'flask',
        'webview',
        'sqlalchemy',
        'reportlab',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Money26',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
