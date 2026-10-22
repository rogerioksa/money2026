# AGENTS.md

Money 2026 — gerenciador financeiro pessoal (Python, Flask + pywebview, SQLite).
UI e docs em pt-BR; identificadores de código em inglês. Pacote Python: `money99`.
Nome exibido do produto: **Money 2026**; pacote, `APP_NAME` e arquivo do banco
continuam `money99` (compatibilidade de dados).
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
  (~1,5 min; timeout de ferramenta ≥ 300000 ms). Saída `dist/Money2026.exe`; fazer smoke:
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

- **Layout/UI**: preservar a estrutura e o histórico das telas (`base.html`,
  `app.js`, `style.css`). Em refatoração, evoluir sem remover rotas, IDs, classes
  ou contratos da API em uso — mudança que quebra o layout só com pedido explícito.
- Dinheiro é inteiro em centavos — nunca `float`; parsing pt-BR só nas bordas
  (`parse_brl`/`format_brl` no backend, `parseBRL`/`fmtMinor` no frontend).
- Datas na API são ISO `AAAA-MM-DD`; exibição BR `DD/MM/AAAA` só no frontend.
- `Transaction.validate()` é a fonte da verdade: valor ≠ 0; transferência não tem
  categoria/splits; splits (≥1, categorias distintas) somam o valor da transação.
  Transação **sem categoria** é válida (pendente de categorização — ex.: importada).
- Sinal: `amount` é assinado do ponto de vista de `account_id` (saída negativa).
  Transferência: uma linha com `transfer_account_id`; a conta destino recebe `-amount`.
- Fim de mês em filtros usa a string `AAAA-MM-31` (comparação lexicográfica) — não
  converter para datas reais.
- Novo endpoint → registrar o blueprint em `api/__init__.py` **e** cobrir em testes.
  Endpoints de escrita commitam no teardown; em erro, rollback (feito em `app.py`).
- Nova coluna → atualizar `models.py` + `db/session._migrate` + `repository` +
  teste de migração legada em `test_db.py` (banco antigo sem a coluna não pode quebrar).
  `_migrate` também faz backfill de `NULL` em colunas numéricas recém-adicionadas
  (SQLite `ADD COLUMN` não aplica DEFAULT a linhas existentes).
- **Manutenção do banco** (`/api/maintenance/*`): backup via
  `sqlite3.Connection.backup()` em `data/backups/`; restauração valida
  `integrity_check`/tabelas e reset recria schema+seed. Restore/reset sempre
  criam backup automático (`pre-restore`/`pre-reset`), limpam a sessão e nunca
  apagam backups. Confirmações obrigatórias: `RESTAURAR` / `APAGAR`.
- **Autenticação**: um usuário local (tabela `users`, PBKDF2 em `services/auth.py`);
  guarda em `app.py` (`before_request`) libera só `/login`, `/static/*` e `/api/auth/*`.
  Sessão via cookie assinado (`SECRET_KEY` em `data/.secret_key`). Testes web usam o
  fixture `client` (já autenticado) ou `anon_client` (sem sessão, `tests/conftest.py`).
- **Perfis**: dados (contas/categorias/transações/orçamentos) são escopados por
  `profile_id`; `Repository(session, profile_id)` e o perfil ativo vem da sessão
  (`PUT /api/auth/profile`). Migração cria perfil "Pessoal" e atribui órfãos a ele.
  Usuários/perfis **não** são escopados. `get_repo()` sem args = perfil atual;
  `get_repo(None)` = sem escopo (uso interno).
- **MEI**: perfil `kind=business`; relatórios em `services/mei.py` (receitas =
  categorias `income`, despesas = `expense`; transferências e sem-categoria
  ignoradas). `annual_limit` em centavos (padrão R$ 81.000,00). O relatório
  mensal segue o **Caderno do MEI** (`monthly_caderno` + `/api/mei/caderno` +
  `/reports/mei?year=&month=`): `profile.activity`
  (`comercio`/`industria`/`servicos`) escolhe as linhas 1-3/4-6/7-9 e
  `Transaction.doc_issued` separa venda com/sem documento fiscal (linhas 1 vs 2).

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
