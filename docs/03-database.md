# 03 — Banco de dados

SQLite + SQLAlchemy 2.0. Um arquivo por empresa (`DB/*.sqlite`).
Código em `src/gnc_lite/db/`: `session.py`, `models.py`, `repository.py`, `chart.py`.

## Conexão e migrações (`session.py`)

- `connect(path)` → engine (`sqlite:///...` ou `sqlite://` p/ `:memory:` nos testes).
- `init_db(engine)` → `create_all` + `_migrate()`: migração leve via
  `PRAGMA table_info(accounts)` + `ALTER TABLE ADD COLUMN` com backfill
  (`kind='normal'`, `credit_limit_minor=0`). **Padrão para evoluir schema sem
  Alembic**: adicionar coluna no model + bloco em `_migrate`. Nunca deletar o
  arquivo do usuário (o reset antigo fazia isso — removido de propósito).
- `make_session(engine)` → `sessionmaker(expire_on_commit=False)`.

## Tabelas (`models.py`)

| Tabela | Colunas-chave | Notas |
|---|---|---|
| `accounts` | id, code (único), name, type, currency, description, placeholder, parent_id (self-FK), **kind**, **credit_limit_minor** | `kind`: `normal\|cartao\|cheque` |
| `transactions` | id, date, description, currency, number, payee, memo | splits com cascade delete-orphan |
| `splits` | id, transaction_id, account_id (index), minor_units, currency, memo | valor com sinal (débito +, crédito −) |
| `parties` | id, name, type (`cliente\|fornecedor`), document, email, phone, notes | |
| `invoices` | id, party_id?, kind (`a_receber\|a_pagar`), minor_units, currency, issue_date, due_date, description, account_id, transaction_id? | |
| `invoice_settlements` | id, invoice_id, date, minor_units, currency, transaction_id? | |
| `users` | id, username (único), display_name, password_hash, role, active | senhas via `security.py` (hash+verify) |

`users` **nunca** é apagada pelo reset (`services/companies.py::reset_company_db`
deleta settlements→invoices→splits→transactions→parties→accounts e resemeia o plano).

## Repository (`repository.py`)

Único acesso ao banco; domínio nunca vê ORM. Principais métodos:

- Contas: `add_account`, `get_account`, `get_account_by_code`, `list_accounts`
  (reconstroi `parent/children`), `account_count`, `update_account`, `has_postings`.
- Lançamentos: `add_transaction` (valida), `get_transaction`, `list_transactions`
  (ordem data,id).
- Somatórios eficientes: `sum_minor_units`, `sum_minor_units_between`,
  `debit_credit_between`, `account_currency`.
- Partes/títulos: `add/get/list_parties`, `add_invoice`, `add_settlement`,
  `get_invoice`, `list_invoices`.
- Usuários: `add/update/get/get_by_username/list/count_users`.

Conversões: `_to_domain_*` (ORM→domínio; conta resolve `kind` com fallback
`"normal"`). `_account_model_for` resolve conta para persistir splits.

## Planos de contas (`chart.py`)

- `CHART_BUSINESS = "empresa"` (24 contas: 1.1 Caixa … 5.5 Impostos) e
  `CHART_PERSONAL = "pessoal"` (doméstico). `chart_for_profile()` em `config.py`
  (MEI→empresa, senão pessoal).
- Hierarquia derivada do código (`parent_code`: `1.2.1`→`1.2`); seed ordena pai→filho.
- Contas `placeholder=True` são grupos (não recebem lançamentos — API e UI barram).
- Tipos: `ativo|passivo|patrimonio|receita|despesa`. Convenção de sinal: **débito
  positivo, crédito negativo** no bruto (`raw`); `natural_balance` aplica o sinal
  natural. Cartão = passivo, cheque especial = ativo (imposto por `ACCOUNT_KIND_TYPE`).
