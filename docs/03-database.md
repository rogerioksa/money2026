# 03 — Banco de dados

SQLite por usuário (`data/money99.sqlite`), SQLAlchemy 2.0 (`db/models.py`).
Na inicialização, `prepare_database()` valida o arquivo, faz backup quando
necessário, roda `init_db()` (`create_all` + `_migrate` + seed) e grava a versão
do schema em `PRAGMA user_version`.

## Tabelas

- **profiles** — `id, name, kind (personal|business), cnpj, legal_name,
  trade_name, opened_on, annual_limit, activity, active`. Separa os dados por
  perfil; `activity` (comercio/industria/servicos) escolhe a seção do Caderno do
  MEI.
- **accounts** — `id, profile_id, name, type, active, credit_limit` e campos
  internos para composição do saldo base.
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

`amount` é assinado do ponto de vista de `account_id`. O saldo exibido de uma
conta considera apenas transações até **hoje**:

```
saldo_base_da_conta
  + SUM(amount WHERE account_id = conta AND date <= hoje)
  + SUM(-amount WHERE transfer_account_id = conta AND date <= hoje)
```

No uso padrão da aplicação, o saldo de abertura é registrado manualmente no
Extrato.

Transações com `date > hoje` não entram no saldo; o repository as expõe em
`future` (`account_balances`) para a interface mostrar como lançamentos futuros.

## Migração e preparação do banco

Na inicialização do EXE, `create_app()` chama `db/session.prepare_database()`:

1. Valida o arquivo com `PRAGMA integrity_check`; se estiver corrompido, aborta
   com erro claro em vez de gravar em cima dos dados.
2. Lê `PRAGMA user_version` e recusa abrir um banco criado por versão mais nova
   do aplicativo (`version > SCHEMA_VERSION`).
3. Se houver tabela/coluna faltante ou o banco vier de versão anterior, copia o
   arquivo via `sqlite3.Connection.backup()` para
   `data/backups/money99-AAAAMMDD-HHMMSS-pre-migration.sqlite`. Backups nunca são
   apagados e aparecem na lista de Configurações → Banco de dados.
4. Roda `init_db()` e grava `PRAGMA user_version = SCHEMA_VERSION`.

`db/session._migrate()` compara as colunas esperadas com as existentes via
`inspect()` e faz `ALTER TABLE ... ADD COLUMN` das que faltarem — nunca apaga
dados; colunas numéricas/booleanas novas também recebem backfill de `NULL`
(`credit_limit`, `activity`, `doc_issued`). Coberto por
`tests/test_db.py::test_legacy_migration_adds_missing_column`,
`::test_legacy_migration_adds_credit_limit`,
`::test_migration_adds_mei_columns` e `::test_prepare_database_backs_up_legacy_and_sets_version`.

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
