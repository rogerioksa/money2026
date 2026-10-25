# 04 — Build, testes e release

## Ambiente

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,build]"   # dev: pytest, ruff · build: pyinstaller
```

Dependências: `SQLAlchemy>=2.0`, `flask>=3.0`, `pywebview>=4.0`.
Ruff: line-length 100, regras `E,F,I,UP,B`.

## Verificação (sempre nesta ordem antes de entregar)

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
node --check "src\money99\web\static\js\app.js"
```

Testes web usam `monkeypatch.chdir(tmp_path)` + `create_app()` + `test_client()`
(fixtures `app`/`client` em `conftest.py`), garantindo isolamento por teste.

## Gerar o EXE

```powershell
money99-build
# ou (manual):
npm run build:css
.\.venv\Scripts\pyinstaller.exe webview_pack.spec --noconfirm --clean
```

- Entry: `src/money99/__main_webview__.py`; `pathex: src`; `datas` embutem
  `web/templates` + `web/static`.
- Saída: `dist/Money2026.exe` (janela, sem console).

## Smoke test (obrigatório pós-build)

```powershell
$p = Start-Process -FilePath "dist\Money2026.exe" -PassThru
Start-Sleep -Seconds 12
if (Get-Process -Id $p.Id -ErrorAction SilentlyContinue) { "RUNNING-OK" } else { "EXITED" }
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
```

## Armadilhas

- O shell é **PowerShell 5.1**: sem `&&` (usar `;`).
- PyInstaller leva ~1,5 min: usar timeout de ferramenta ≥ 300000 ms.
- SQLite do usuário: `init_db` migra colunas; jamais deletar o banco real.
