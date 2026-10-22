# 03 — Banco de dados

SQLite por usuário (`data/money99.sqlite`), SQLAlchemy 2.0 (`db/models.py`).
`init_db()` roda `Base.metadata.create_all` + `_migrate` + seed de categorias.

## Tabelas

- **profiles** — `id, name, kind (personal|business), cnpj, legal_name,
  trade_name, opened_on, annual_limit, activity, active`. Separa os dados por
  perfil; `activity` (comercio/industria/servicos) escolhe a seção do Caderno do
  MEI.
- **accounts** — `id, profile_id, name, type, initial_balance, active, credit_limit`.
  `credit_limit` (centavos) é o limite de crédito/cheque especial; o painel mostra
  `available = saldo + limite` em todas as contas.
- **categories** — `id, profile_id, name, kind (income|expense), parent_id`.
- **transactions** — `id, profile_id, date (ISO), description, account_id, amount
  (centavos), category_id, transfer_account_id, notes, reconciled, doc_issued`.
  `doc_issued` (MEI) indica venda com documento fiscal (PJ).
- **splits** — `id, transaction_id, category_id, amount`.
- **budgets** — `id, profile_id, year, month, category_id, planned`.
- **users** — `id, username (único), password_hash, salt`. Senha nunca em claro
  (PBKDF2-SHA256, `services/auth.py`).

## Perfis (isolamento)

Contas, categorias, transações e orçamentos carregam `profile_id`. O `Repository`
é escopado por perfil (`Repository(session, profile_id)`), e o perfil ativo vem da
sessão (`app.py`). Migração de banco antigo cria o perfil "Pessoal" e atribui as
linhas órfãs a ele (`_seed_profiles`).

## Sinal e saldo

`amount` é assinado do ponto de vista de `account_id`. O saldo de uma conta é:

```
initial_balance
  + SUM(amount WHERE account_id = conta)
  + SUM(-amount WHERE transfer_account_id = conta)
```

## Migração

`db/session._migrate()` compara as colunas esperadas com as existentes via
`inspect()` e faz `ALTER TABLE ... ADD COLUMN` das que faltarem — nunca apaga
dados; colunas numericas/booleanas novas tambem recebem backfill de `NULL`
(`credit_limit`, `activity`, `doc_issued`). Coberto por
`tests/test_db.py::test_legacy_migration_adds_missing_column`,
`::test_legacy_migration_adds_credit_limit` e `::test_migration_adds_mei_columns`.

## Seed

`DEFAULT_CATEGORIES` (12 categorias de receita/despesa) é inserido apenas se a
tabela `categories` estiver vazia.

## Backup, restauração e reset

Configurações → **Banco de dados** (`/api/maintenance/*`) permite:

- **Backup**: copia consistente via `sqlite3.Connection.backup()` para
  `data/backups/money99-AAAAMMDD-HHMMSS.sqlite` (não usa cópia simples do
  arquivo). A lista mostra caminho, tamanho e data.
- **Restauração**: por um backup da lista ou upload de `.sqlite`; valida
  `integrity_check` e as tabelas obrigatórias, cria backup `pre-restore` e só
  então substitui o arquivo. Em falha, tenta voltar ao backup de segurança.
- **Reset**: cria backup `pre-reset`, apaga `data/money99.sqlite` e roda
  `init_db()` (schema + seed). O login também é apagado; a SPA volta ao setup.
- Backups nunca são apagados pelo reset.

## Regra do .gitignore

O diretório de dados chama-se `data/`. **Nunca** colocar `DB/` no `.gitignore`:
no Windows (case-insensitive) casaria com o pacote de código `src/money99/db/`.
