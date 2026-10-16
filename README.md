# Money 26

Contabilidade de **partidas dobradas** simples, em Python, para pequenos negocios.

Inspirado no [GnuCash](https://github.com/Gnucash/gnucash), mas com foco em
simplicidade: nucleo contabil enxuto, persistencia local (SQLite) e interface
web local (Flask + pywebview).

## Estado

Projeto em desenvolvimento. Fases:

- [x] **Fase 0** - esqueleto do projeto (packaging, lint, testes)
- [x] **Fase 1** - dominio contabil (contas, lancamentos, partidas dobradas)
- [x] **Fase 2** - persistencia (SQLAlchemy + SQLite + plano de contas padrao)
- [x] **Fase 3** - interface (janela principal, contas, registro)
- [x] **Fase 4** - relatorios (balancete, DRE, balanco, fluxo de caixa)
- [x] **Fase 5** - clientes/fornecedores e contas a pagar/receber
- [x] **Fase 6** - import/export (CSV/QIF/OFX) e relatorios em PDF

## Requisitos

- Python 3.11+
- Instalacao: `pip install -e ".[dev,build]"`
- Execucao: `gnc-lite` (abre janela pywebview) ou `python -m gnc_lite.__main_webview__`

## Uso

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,build]"
gnc-lite
pytest
ruff check .
```

Os dados ficam em `%APPDATA%\GnuCashLite\gnc_lite.sqlite` (primeira execucao cria o plano de contas padrao).

## Gerar o executavel (.exe)

```powershell
pip install -e ".[build]"
pyinstaller webview_pack.spec --noconfirm --clean
```

O resultado fica em `dist\Money26.exe` (arquivo unico). E um app de janela
(pywebview, sem console); na primeira execucao cria o banco em `%APPDATA%\GnuCashLite`.

## Estrutura

```
src/gnc_lite/
  domain/       # regras contabeis puras (contas, lancamentos, titulos, partes)
  db/           # SQLAlchemy + SQLite: models, repository, chart (plano de contas)
  services/     # ledger, billing (contas a receber/pagar), reports, importer, exporter, pdf
  api/          # REST Flask consumida pelo frontend web
  web/          # templates/static do frontend (SPA)
  app_webview.py  # Flask + launcher pywebview
  main.py
tests/
```

## Documentação

Guias de manutenção em `docs/` (arquitetura, API, banco, frontend, build,
operações e guia para agentes IA):

- `docs/00-overview.md` — visão geral e mapa do repositório
- `docs/01-architecture.md` — camadas, sessão web e invariantes
- `docs/02-backend-api.md` — referência completa dos endpoints
- `docs/03-database.md` — modelos, migrações e planos de contas
- `docs/04-domain-services.md` — regras contábeis e serviços
- `docs/05-frontend.md` — SPA, telas e convenções
- `docs/06-build-release.md` — testes, lint, build e smoke
- `docs/07-operations.md` — dados, troubleshooting e FAQ
- `docs/08-ai-agent-guide.md` — como um agente IA deve trabalhar aqui
- `docs/09-decisions.md` — decisões arquiteturais (ADRs)

## Licenca

GPL-3.0-or-later (compativel com o GnuCash original).
