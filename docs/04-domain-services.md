# 04 — Domínio e serviços

## Domínio (`domain/`) — regras puras, sem I/O

- **`money.py`**: `Money(minor_units, currency="BRL")` imutável; `from_decimal`,
  `amount`, `is_zero`, aritmética com checagem de moeda. **Nunca `float`.**
- **`account.py`**: `AccountType` + `Account`. Constantes de natureza especial:
  `ACCOUNT_KIND_NORMAL/CARD/OVERDRAFT` (`normal|cartao|cheque`), labels e
  `ACCOUNT_KIND_TYPE` (cartão→passivo, cheque→ativo). Helpers:
  `is_special`, `used_credit_minor(raw)` = `max(0, -raw)`,
  `available_credit_minor(raw)` = limite − usado (`None` sem limite).
- **`transaction.py`**: `Transaction(date, description, payee, splits)` +
  `validate()` (soma zero); `Split(account, amount, memo)`.
- **`invoice.py`**: `InvoiceKind` (`a_receber|a_pagar`), `InvoiceStatus`
  (`aberto|parcial|quitado` derivado de `settled_amount` vs `amount`),
  `open_amount`, `is_overdue(today)`.
- **`party.py`**: `Party` + `PartyType` (`cliente|fornecedor`).
- **`user.py`**: `Role` (`admin|operador|consulta`) com `can_write`
  (admin+operador), `is_admin`, `label`; `User` com `display_name`
  (exibir via `display_name or username`).
- **`errors.py`**: `GncLiteError` e especializações (`UserError`, `InvoiceError`,
  `ImportParseError`…). Serviços lançam; API traduz em 400.

## Serviços (`services/`)

- **`ledger.py`** — fachada: `create_account(..., kind?, credit_limit_minor?)`,
  `update_account`, `has_postings`, `post/post_many`, `transactions`,
  `raw_balance[_in_range|_asof]`, `balance[_in_range]`, `movements`.
- **`billing.py`** — `BillingService`: `create_party/parties`,
  `issue_receivable/issue_payable` (posta emissão contra 1.3/2.1 e 4.1/5.1 por padrão),
  `settle` (total/parcial, valida teto e valor positivo), `invoices/open_invoices`.
- **`reports.py`** — constrói `Report(title, columns, rows, footer, period, info, notes)`:
  `trial_balance`, `income_statement(start,end)`, `balance_sheet(asof)`,
  `cash_flow(start,end)` (contas `_is_cash`: `1.1*`/`1.2*`), `open_items`, `period_label`.
- **`mei.py`** — `revenue_entries(ledger,start,end)` (créditos em contas INCOME),
  `classify_code` (4.1=comércio, 4.2=serviços), `effective_annual_limit`
  (proporcional ao mês de início), `billing_report` (RMR mensal art. 54),
  `annual_report`, `document_map` (doc do comprador via títulos).
- **`importer.py`** — `read_transactions_csv` (linhas agrupadas por `ref`),
  `read_qif` (categoria `L` resolvida no plano), `read_ofx`, `import_*_file`
  (utf-8-sig→latin-1), `transaction_signature` + `partition_new` (anti-duplicado).
- **`exporter.py`** — `transactions_to_csv`, `write_transactions_csv`,
  `report_to_html`, `write_report_pdf` (delega a `pdf.py`/reportlab).
- **`pdf.py`** — `report_to_pdf` (reportlab, paisagem A4). Sem Qt.
- **`auth.py`** — `AuthService`: `create_user`, `authenticate`, `list_users`,
  `set_password/set_active/set_role/rename` (senha mín. 4).
- **`companies.py`** — `data_directory()` (`<exe>/DB`, fallback APPDATA),
  `CompanyRegistry` (JSON), `create_company` (banco+plano+admin),
  `reset_company_db` (zera contábil, **mantém usuários**).
- **`config.py`** — `AppConfig`+`Profile` em `%APPDATA%/GnuCashLite/config.json`:
  perfil, dados MEI, `mei_limite_anual` (padrão 81.000), `chart_for_profile`.
- **`obligations.py`** — DAS/RMR (venc. dia 20) + DASN ano anterior (31/05);
  `compute/compute_with_records` (status por `today` injetável p/ testes),
  `mark/load/save_records` em `<banco>.obrigacoes.json`, `das_csv_text`.
- **`cnpj.py`** — Minha Receita `GET /<cnpj>` (12s timeout, sem auth):
  `normalize` (valida dígitos), `lookup`, `summarize` (ficha completa),
  `format_cnpj`, cache `<banco>.cnpj.json` + `is_stale` (30 dias).
- **`security.py`** — hash/verificação de senhas. **`data_path.py`** (raiz do pacote) —
  `exports_dir()`, `open_for_print()` (53708-xxxxx no Windows).
