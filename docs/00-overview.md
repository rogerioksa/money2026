# 00 — Visão geral

Money 2026 é um gerenciador financeiro pessoal em Python, inspirado no Microsoft
Money: contas, transações com categorias/transferências/splits, orçamentos
mensais, relatórios e importação de extratos QIF/OFX.

| Item | Valor |
|---|---|
| Pacote Python | `money99` |
| Interface | SPA em `web/` servida por Flask, aberta em janela pywebview |
| Banco | SQLite (`data/money99.sqlite`), via SQLAlchemy 2.0 |
| Dinheiro | Inteiro em centavos — nunca `float` |
| Idioma/moeda | pt-BR / BRL |
| Executável | `dist/Money2026.exe` (PyInstaller, `webview_pack.spec`) |
| Python | 3.11+ |

## Estrutura

```
src/money99/
  main.py / __main_webview__.py   # entrypoints (CLI e PyInstaller)
  app.py                          # create_app() + launcher pywebview
  data_path.py                    # pasta de dados gravável
  domain/                         # regras puras (money, account, transaction, budget)
  db/                             # models, repository, session (_migrate + seed)
  services/                       # budget, reports, importer, reconcile
  api/                            # blueprints REST
  web/                            # templates/base.html + static/{css,js}
tests/                            # pytest
docs/                             # esta documentação
webview_pack.spec                 # build do Money2026.exe
```

## Telas (SPA, hash-routes)

- `#/contas` — CRUD de contas com saldo.
- `#/extrato` — transações com filtros, lançamento rápido e conciliação.
- `#/orcamento` — planejado × realizado por categoria/mês.
- `#/relatorios` — gastos por categoria, patrimônio líquido, fluxo de caixa (canvas).
- `#/importar` — preview e importação de extrato QIF/OFX.

## Dados em runtime

- Banco: `data/money99.sqlite` (ao lado do cwd/exe; fallback `%APPDATA%/Money99`).
- Exportações: `data/exports/`.
- Backups: `data/backups/` (criados em Configurações → Banco de dados).
