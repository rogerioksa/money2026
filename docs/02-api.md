# 02 — API REST

Todos os endpoints são JSON em `/api/*` (exceto `GET /`, que serve a SPA).
Dinheiro em centavos (int); datas em ISO `AAAA-MM-DD`.

## Contas — `/api/accounts`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/accounts[?active=1]` | Lista contas com `balance`. |
| POST | `/api/accounts` | Cria conta `{name, type, initial_balance}`. |
| GET | `/api/accounts/<id>` | Detalhe. |
| PUT | `/api/accounts/<id>` | Atualiza. |
| DELETE | `/api/accounts/<id>` | Exclui (400 se tiver transações). |
| GET | `/api/accounts/<id>/balance` | `{balance}`. |
| GET | `/api/accounts/<id>/reconciliation` | Resumo de conciliação. |

`type`: `bank|credit|cash|asset|investment`.

## Categorias — `/api/categories`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/categories[?kind=income\|expense]` | Lista. |
| POST | `/api/categories` | Cria `{name, kind, parent_id?}`. |

## Transações — `/api/transactions`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/transactions?account_id&category_id&start&end&reconciled` | Lista/filtra. |
| POST | `/api/transactions` | Cria (valida invariantes). |
| PUT | `/api/transactions/<id>` | Atualiza. |
| DELETE | `/api/transactions/<id>` | Exclui. |
| POST | `/api/transactions/<id>/reconcile` | `{reconciled: bool}`. |

## Orçamentos — `/api/budgets`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/budgets?year&month` | Planejado × realizado por categoria. |
| PUT | `/api/budgets` | `{year, month, category_id, planned}`. |

## Relatórios — `/api/reports`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/reports/spending?start&end[&kind]` | Total por categoria. |
| GET | `/api/reports/net-worth[?as_of]` | Patrimônio líquido. |
| GET | `/api/reports/cash-flow?start&end` | Entradas/saídas por mês. |

## Importação — `/api/import`

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/import/preview` | `{content, filename}` → transações parseadas. |
| POST | `/api/import/commit` | `{account_id, default_category_id, transactions}`. |

Erros retornam `{"error": "..."}` com status 400/404.
