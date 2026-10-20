# 03 — Banco de dados

SQLite por usuário (`data/money99.sqlite`), SQLAlchemy 2.0 (`db/models.py`).
`init_db()` roda `Base.metadata.create_all` + `_migrate` + seed de categorias.

## Tabelas

- **accounts** — `id, name, type, initial_balance, active`.
- **categories** — `id, name, kind (income|expense), parent_id`.
- **transactions** — `id, date (ISO), description, account_id, amount (centavos),
  category_id, transfer_account_id, notes, reconciled`.
- **splits** — `id, transaction_id, category_id, amount`.
- **budgets** — `id, year, month, category_id, planned`.

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
dados. Coberto por `tests/test_db.py::test_legacy_migration_adds_missing_column`.

## Seed

`DEFAULT_CATEGORIES` (12 categorias de receita/despesa) é inserido apenas se a
tabela `categories` estiver vazia.

## Regra do .gitignore

O diretório de dados chama-se `data/`. **Nunca** colocar `DB/` no `.gitignore`:
no Windows (case-insensitive) casaria com o pacote de código `src/money99/db/`.
