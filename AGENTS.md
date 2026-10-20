# AGENTS.md

Money 99 — gerenciador financeiro pessoal (Python, Flask + pywebview, SQLite).
UI e docs em pt-BR; identificadores de código em inglês. Pacote Python: `money99`.
Roda como janela nativa — não há URL de servidor para navegar.

## Setup e comandos (Windows / PowerShell 5.1)

- Venv existente: `.\.venv\Scripts\python.exe` (Python 3.14 instalado; requer 3.11+).
- Instalar: `pip install -e ".[dev,build]"` (dev: pytest/ruff; build: pyinstaller).
- Rodar: `money99` ou `.\.venv\Scripts\python.exe -m money99.__main_webview__`.
- Verificar antes de entregar, nesta ordem:
  1. `.\.venv\Scripts\python.exe -m pytest -q`
  2. `.\.venv\Scripts\python.exe -m ruff check src tests`
  3. `node --check "src\money99\web\static\js\app.js"`
- Teste focado: `.\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -q` (ou `-k nome`).
- Build EXE: `.\.venv\Scripts\pyinstaller.exe webview_pack.spec --noconfirm --clean`
  (~1,5 min; timeout de ferramenta ≥ 300000 ms). Saída `dist/Money99.exe`; fazer smoke:
  iniciar o processo, esperar ~12 s e conferir que segue vivo (`RUNNING-OK`).

## Layout

- `src/money99/domain/` — regras puras (sem Flask/SQLAlchemy): `money`, `account`,
  `transaction`, `budget`.
- `src/money99/db/` — `models.py`, `repository.py`, `session.py` (`_migrate` + seed).
- `src/money99/services/` — `budget`, `reports`, `importer`, `reconcile`.
- `src/money99/api/` — blueprints Flask finos; helpers em `_common.py`.
- `src/money99/web/` — SPA: `templates/base.html` + `static/js/app.js` + `static/css`.
- `src/money99/app.py` — `create_app()` (engine + sessão por request) e launcher pywebview.
- `tests/` — pytest; testes web usam as fixtures `app`/`client` de `conftest.py`
  (que fazem `monkeypatch.chdir(tmp_path)` + `create_app()`).

## Invariantes (não quebrar)

- Dinheiro é inteiro em centavos — nunca `float`; parsing pt-BR só nas bordas
  (`parse_brl`/`format_brl` no backend, `parseBRL`/`fmtMinor` no frontend).
- Datas na API são ISO `AAAA-MM-DD`; exibição BR `DD/MM/AAAA` só no frontend.
- `Transaction.validate()` é a fonte da verdade: valor ≠ 0; transferência não tem
  categoria/splits; splits (≥1, categorias distintas) somam o valor da transação.
- Sinal: `amount` é assinado do ponto de vista de `account_id` (saída negativa).
  Transferência: uma linha com `transfer_account_id`; a conta destino recebe `-amount`.
- Fim de mês em filtros usa a string `AAAA-MM-31` (comparação lexicográfica) — não
  converter para datas reais.
- Novo endpoint → registrar o blueprint em `api/__init__.py` **e** cobrir em testes.
  Endpoints de escrita commitam no teardown; em erro, rollback (feito em `app.py`).
- Nova coluna → atualizar `models.py` + `db/session._migrate` + `repository` +
  teste de migração legada em `test_db.py` (banco antigo sem a coluna não pode quebrar).

## Proibições

- ⚠️ **NUNCA** adicionar `DB/` ou qualquer padrão case-insensitive que case com o
  pacote `src/money99/db/` ao `.gitignore` (Windows `core.ignorecase=true`). O
  diretório de dados em runtime chama-se `data/`. Essa foi a causa de perder o
  pacote `db/` de um projeto anterior.
- Não renomear o pacote `money99`, `APP_NAME` ou a pasta de dados (quebra dados).
- Frontend não baixa via blob (pywebview ignora) — expor endpoint dedicado.
- Sem `float` para dinheiro; sem datas não-ISO na API.
- Não commitar/push/PR sem pedido explícito.
- Não usar `Select-Object -First` para "economizar" saída do pytest (o resumo fica no fim).

## Docs

Guias curtos em `docs/`: `00-overview`, `01-architecture`, `02-api`, `03-database`,
`04-build`. Em conflito entre docs e código/testes, confiar no código/testes.
