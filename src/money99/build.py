"""Build helper: compila CSS e gera EXE com PyInstaller."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], *, cwd: Path) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build do Money 2026: CSS Tailwind + EXE PyInstaller"
    )
    parser.add_argument(
        "--skip-css",
        action="store_true",
        help="pula a etapa npm run build:css",
    )
    parser.add_argument(
        "--skip-exe",
        action="store_true",
        help="pula a etapa de geração do executável",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]

    if not args.skip_css:
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        _run([npm_cmd, "run", "build:css"], cwd=project_root)

    if not args.skip_exe:
        pyinstaller = project_root / ".venv" / "Scripts" / "pyinstaller.exe"
        if pyinstaller.exists():
            cmd = [str(pyinstaller), "webview_pack.spec", "--noconfirm", "--clean"]
        else:
            cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "webview_pack.spec",
            "--noconfirm",
            "--clean",
        ]
        _run(cmd, cwd=project_root)

    print("Build concluido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
