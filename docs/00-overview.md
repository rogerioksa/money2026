# 00 — Visão geral do Money 26

> Contabilidade de **partidas dobradas** em Python para pequenos negócios e MEI,
> com interface web local (Flask + pywebview) empacotada em `.exe` único.

## Produto em 30 segundos

| Item | Valor |
|---|---|
| Nome do produto | **Money 26** |
| Pacote Python (interno) | `gnc_lite` (mantido por compatibilidade) |
| Interface | SPA em `web/` servida por Flask, aberta em janela pywebview |
| Banco | SQLite por empresa (`DB/*.sqlite`), via SQLAlchemy 2.0 |
| Dinheiro | Inteiros (centavos) — nunca `float` (`domain/money.py`) |
| Idioma/moeda | pt-BR, BRL |
| Executável | `dist/Money26.exe` (PyInstaller, `webview_pack.spec`) |
| Python | 3.11+ (desenvolvimento em 3.12, `.venv`) |

## Perfis de uso

- **Uso pessoal** (`Profile.PERSONAL`): plano de contas simplificado, sem telas de empresa.
- **MEI** (`Profile.MEI`): plano empresarial completo + Títulos, Empresas, Obrigações
  (DAS/RMR/DASN-SIMEI), relatórios MEI e consulta de CNPJ.

Regra de ouro da UX: **telas de empresa (Empresas, Títulos, Obrigações) só aparecem
no perfil MEI**. Relatórios MEI idem. Implementado em `web/static/js/app.js`
(`MEI_ROUTES`, `data-mei`, `syncProfile()`).

## Estrutura do repositório

```
├── src/gnc_lite/
│   ├── main.py               # entrypoint `gnc-lite` → run_webview()
│   ├── __main_webview__.py   # entrypoint do PyInstaller → run_webview()
│   ├── app_webview.py        # Flask + launcher pywebview + WebSession
│   ├── data_path.py          # exports/ + abrir-no-programa-padrão
│   ├── api/                  # blueprints REST (10 arquivos)
│   ├── db/                   # chart, models, repository, session
│   ├── domain/               # regras puras (account, money, transaction, ...)
│   ├── services/             # ledger, billing, reports, mei, importer, ...
│   └── web/                  # templates/base.html + static/{css,js}
├── tests/                    # 14 arquivos de teste (ver 06-build-release.md)
├── docs/                     # esta documentação
├── webview_pack.spec         # build do Money26.exe
├── pyproject.toml            # deps: SQLAlchemy, flask, pywebview, reportlab
└── dist/Money26.exe          # artefato gerado (não versionar conteúdo)
```

## Onde ficam os dados (runtime)

- Bancos: `<pasta do exe>/DB/*.sqlite` (dev: `<cwd>/DB/`); fallback
  `%APPDATA%/GnuCashLite/` se `DB/` não for gravável. Migração automática do legado.
- Registro de empresas: `DB/empresas.json`.
- Config (perfil + MEI): `%APPDATA%/GnuCashLite/config.json` (sempre global, não por empresa).
- Sidecars por empresa: `<banco>.obrigacoes.json` (DAS/RMR/DASN marcados),
  `<banco>.cnpj.json` (cache Minha Receita).
- Exportações: `DB/exports/` (CSV DAS, ficha CNPJ JSON).

## Documentos seguintes

- `01-architecture.md` — camadas, sessão web, ciclo de request.
- `02-backend-api.md` — referência completa dos endpoints.
- `03-database.md` — modelos, migrações, planos de contas.
- `04-domain-services.md` — regras contábeis e serviços.
- `05-frontend.md` — SPA, telas, convenções JS/CSS.
- `06-build-release.md` — venv, testes, lint, build, smoke.
- `07-operations.md` — dados em produção, troubleshooting, FAQ.
- `08-ai-agent-guide.md` — como um agente IA deve trabalhar aqui.
- `09-decisions.md` — decisões arquiteturais registradas (ADRs).
