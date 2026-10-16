# 06 — Build, testes e release

## Ambiente

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,build]"   # dev: pytest, ruff, alembic · build: pyinstaller
```

Dependências de runtime (`pyproject.toml`): `SQLAlchemy>=2.0`, `flask>=3.0`,
`pywebview>=4.0`, `reportlab>=4.0`. `ruff`: line-length 100, regras `E,F,I,UP,B`.

## Comandos (sempre nesta ordem antes de entregar)

```powershell
.\.venv\Scripts\python.exe -m pytest -q          # ~78 testes, <1 min
.\.venv\Scripts\python.exe -m ruff check src tests
node --check "src\gnc_lite\web\static\js\app.js" # sintaxe do frontend
```

Testes por arquivo (`tests/`): `test_billing`, `test_chart_profiles`,
`test_companies_db`, `test_config`, `test_db` (inclui migração legada),
`test_import_encoding`, `test_io` (+PDF reportlab), `test_mei`, `test_money`,
`test_obligations` (DAS/RMR/DASN + CNPJ), `test_reports`, `test_transaction`,
`test_web_api` (regressão ponta-a-ponta da API: auth, contas, relatórios,
títulos, usuários, config, reset, DAS CSV, CNPJ fill, cartão/limite).

Padrão de teste web: `monkeypatch.chdir(tmp_path)` + `app_webview.create_app()`
+ `test_client()` (isolamento total por teste). Rede nunca é chamada de verdade
(monkeypatch em `cnpj.lookup`).

## Gerar o EXE

```powershell
.\.venv\Scripts\pyinstaller.exe webview_pack.spec --noconfirm --clean  # ~5-10 min
```

- Entry: `src/gnc_lite/__main_webview__.py`; `pathex: src`; `datas` embutem
  `web/templates` + `web/static`; `hiddenimports`: flask, webview, sqlalchemy, reportlab.
- Saída: `dist/Money26.exe` (~30 MB, janela, sem console). Apagar EXEs com nome
  antigo se existirem (`dist/GnuCashLite-Web.exe` foi descontinuado).

## Smoke test (obrigatório pós-build)

```powershell
$p = Start-Process -FilePath "dist\Money26.exe" -PassThru
Start-Sleep -Seconds 12
if (Get-Process -Id $p.Id -ErrorAction SilentlyContinue) { "RUNNING-OK" } else { "EXITED" }
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
```

Extras semanais: login→`me`→logout via `test_client`; `GET /` e estáticos 200;
importação QIF→classificação→relatórios com dados reais do usuário quando possível.

## Armadilhas conhecidas

- `bash` aqui é **PowerShell 5.1**: sem `&&` (usar `;`), sem `tail` (usar
  `Select-Object -Last N`), `2>&1` dentro de strings gera erro de parse em alguns
  contextos — preferir comandos simples.
- PyInstaller >2 min: a ferramenta tem timeout configurável (usar 900000 ms).
- `os.startfile` só existe no Windows (guardar por `os.name`, como em `data_path.py`).
- SQLite antigo do usuário: `init_db` migra colunas; jamais `unlink()` no banco real.
