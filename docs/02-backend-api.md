# 02 — Referência da API REST

Base: `http://127.0.0.1:<porta>/api`. Arquivos em `src/gnc_lite/api/`.
Erros: `{"error": "..."}` com 400/401/403/404; 500 vira `{"error":"internal_error"}`.

## Empresas — `companies_bp.py` (`/api/companies`)

| Método | Rota | Corpo | Resposta |
|---|---|---|---|
| GET | `/api/companies` | — | `{companies: [{id, name, db_path}]}` |
| POST | `/api/companies` | `{name, admin_user, admin_pass}` | `{ok, company}` — cria banco + plano + admin (400 se inválido) |
| POST | `/api/companies/select` | `{company_id}` | `{ok, company}` — troca ativa (404 sem empresa; preserva login se mesma) |
| POST | `/api/companies/reset` | — | `{ok}` — **admin**: zera lançamentos/títulos/partes/contas e recria o plano; **usuários mantidos**, sessão continua logada |

## Auth — `auth_bp.py` (`/api/auth`)

| Método | Rota | Corpo | Resposta |
|---|---|---|---|
| POST | `/api/auth/login` | `{username, password}` | `{ok, user}` (401 inválido; 400 sem empresa) |
| GET | `/api/auth/me` | — | `{user \| null}` — `user: {id, username, display, role, can_write, is_admin}` |
| POST | `/api/auth/logout` | — | `{ok}` |

## Usuários — `users_bp.py` (`/api/users`, só admin)

- `GET /api/users` → `{users: [{id, username, display, role, active, can_write, is_admin}]}`
- `POST /api/users` `{username, password, role, display?}` → `{ok, user}` (papéis: `admin|operador|consulta`)
- `PATCH /api/users/<id>` `{role?, active?, password?, username?, display?}`

## Contas — `accounts_bp.py` (`/api/accounts`)

`GET /api/accounts` → `{accounts: [...]}` ordenado por código. Cada conta:

```json
{ "id": 1, "code": "1.1", "name": "Caixa", "type": "ativo", "type_label": "ativo",
  "placeholder": false, "parent_id": 7, "currency": "BRL", "balance_minor": 10000,
  "description": "", "kind": "normal", "kind_label": "Padrão",
  "limit_minor": 0, "used_minor": 0, "available_minor": null }
```

- `kind`: `normal|cartao|cheque` (cartão força tipo **passivo**, cheque **ativo**).
- `used_minor` = dívida atual; `available_minor` = limite − usado (`null` sem limite).
- `POST /api/accounts` `{code, name, type?, kind?, limit_minor?, parent_id?, description?, placeholder?}`
  (400 em código duplicado/tipo inválido).
- `PATCH /api/accounts/<id>` `{name?, description?, placeholder?, kind?, limit_minor?}`.

## Lançamentos — `transactions_bp.py` (`/api/transactions`)

- `GET /api/transactions` → últimos 200 `{id, date, description, payee, splits[]}`
  (`splits: [{account_id, account_code, account_name, minor_units}]`).
- `POST /api/transactions` `{date, description?, payee?, splits: [{account_id, minor_units}]}` (valida balanceamento).
- `POST /api/transactions/many` `{transactions: [...]}` (splits duplos; ignora inválidos).
- `GET /api/transactions/running-balance?account_id=` → `{rows: [{id, date, description, payee, transfer, debit, credit, balance}]}` em ordem cronológica acumulada (`transfer` = contrapartida ou "N contas").

## Importação — `import_bp.py` (`/api/import`, multipart)

- `POST /api/import/csv` (só `file`) — CSV com colunas `ref,date,account,amount` (+`description,payee,memo`); `ref` agrupa partidas.
- `POST /api/import/qif` (`file` + `account_id`) — categoria `L` do arquivo quando existe no plano.
- `POST /api/import/ofx` (`file` + `account_id` + `counter_account_id`).
- Resposta: `{posted, skipped, transaction_ids}` — duplicados por assinatura
  (data+descrição+payee+splits) são ignorados (`partition_new`). Encoding: utf-8-sig com fallback latin-1.

## Títulos — `invoices_bp.py` (`/api/invoices`)

- Partes: `GET /api/invoices/parties?type=` · `POST /api/invoices/parties` `{name, type: cliente|fornecedor, document?, email?, phone?, notes?}`.
- `GET /api/invoices?kind=a_receber|a_pagar&open_only=1` → `{invoices: [{id, kind, kind_label, amount_minor, open_minor, settled_minor, issue_date, due_date, party_id, party_name, description, status}]}` (`aberto|parcial|quitado`).
- `POST /api/invoices/receivable|payable` `{party_id, amount_minor>0, issue_date, due_date, description?, currency?, income_account_id?/expense_account_id?, receivable_account_id?/payable_account_id?}` — já posta o lançamento de emissão.
- `POST /api/invoices/<id>/settle` `{date, cash_account_id, amount_minor?}` — baixa total ou parcial (valida teto).

## Relatórios — `reports_bp.py` (`/api/reports`)

JSON genérico: `{title, columns, rows: [[{text, minor|null}]], footer?, period, info, notes}`.
- `GET /status`, `/trial-balance`, `/income?start&end`, `/balance-sheet?asof`,
  `/cash-flow?start&end`, `/mei-monthly?year&month` (RMR), `/mei-annual?year`.

## Obrigações — `obligations_bp.py` (`/api/obligations`)

- `GET /api/obligations?year&month` → `{obligations: [{key, kind: das|rmr|dasn, title, period, due, status: concluida|pendente|atrasada, detail, amount_minor}]}` (DAS e RMR vencem dia 20; DASN ano anterior vence 31/05, com % do limite).
- `POST /api/obligations/mark` `{key, done}` — persiste em `<banco>.obrigacoes.json`.

## CNPJ — `cnpj_bp.py` (`/api/cnpj`, Minha Receita, sem auth, timeout 12s)

- `GET /api/cnpj/status[?auto=1]` → `{configured, cnpj, cached {cnpj, checked_at, result}, stale}` (auto atualiza se obsoleto >30d).
- `POST /api/cnpj/check` `{cnpj?}` → consulta agora e cacheia (502 se API fora).
- `POST /api/cnpj/fill` `{cnpj?}` → `{fields: {nome_empresarial, cnpj, atividade, municipio, uf, inicio_atividade}, filled[], warnings[]}` (não salva; avisa se não optante MEI).

## Config — `config_bp.py` (`/api/config`)

- `GET` → `{profile: pessoal|mei, profile_label, mei: {nome_empresarial, cnpj, atividade, municipio, uf, inicio_atividade, limite_anual_minor}}`.
- `PUT` parcial (mesmo formato); valida perfil, data e limite.

## Exportações — `exports_bp.py` (`/api/exports`, arquivos em `DB/exports/`)

O webview não trata download de blob: exportações **salvam em disco** e a UI oferece abrir.
- `POST /api/exports/das-csv` `{year}` → `{ok, filename: DAS_<ano>_situacao.csv, path}`.
- `POST /api/exports/cnpj-ficha` `{cnpj?}` → `{ok, filename: CNPJ_<digits>_ficha.json, path}`.
- `GET /api/exports/open?file=` → abre no programa padrão (404 se ausente; 400 em nome inválido; traversal neutralizado via basename).
