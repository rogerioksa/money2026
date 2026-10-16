# 05 — Frontend (SPA)

Vanilla JS + CSS, sem framework: `web/templates/base.html`,
`web/static/css/style.css`, `web/static/js/app.js` (~900 linhas).
Embutidos no EXE via `webview_pack.spec` (`datas`).

## Layout (`base.html`)

Sidebar (`#menu`: Registro, Contas, Títulos, Relatórios, Obrigações, Importar,
Empresas, Configurações) + topbar (`#company-select`, `#user-info`, `#btn-logout`)
+ `<main id="app">` + `#toasts`. Links com `data-route` e `data-mei="1"` nos
exclusivos do MEI (Títulos, Obrigações, Empresas).

## Estado e boot (`app.js`)

- `state = {companies, companyId (localStorage), user, accounts, accountId, isMei}`.
- `boot()` → `refreshSession()` (empresas → select → `me` → contas → `syncProfile()`)
  → `route()`. `updateTopbar()` preenche seletor/usuário.
- `route()` lê `location.hash`, aplica `auth-mode` no `<body>` quando deslogado
  (esconde sidebar+topbar, centraliza login) e barra `MEI_ROUTES` no pessoal
  (toast + volta ao Registro).
- `setMenu()` marca ativo e esconde links `data-mei` fora do MEI.
- Trocar perfil em Configurações atualiza `state.isMei` na hora (`route()` re-renderiza).

## Telas (`render*`)

| Hash | Tela | Destaques |
|---|---|---|
| `#/login` | Entrar | usuário+senha; Enter envia |
| `#/companies` | Empresas | tabela + criar (nome/admin/senha) + abrir |
| `#/register` | Registro | seletor de conta, painel de limite (cartão/cheque), form de lançamento (data, payee, descrição, transferência, débito **ou** crédito), tabela com transferência e subtotal |
| `#/accounts` | Contas | tabela (saldo, limite, disponível, badges), criar (código/nome/natureza/tipo/pai/limite), renomear e editar limite |
| `#/invoices` | Títulos | a receber/a pagar em aberto, emitir, baixar (total/parcial), nova parte |
| `#/reports` | Relatórios | balancete/DRE/balanço/fluxo + RMR/anual (só MEI), filtros de período |
| `#/obligations` | Obrigações (MEI) | DAS/RMR/DASN com badges, marcar pago/arquivado/entregue, **baixar lista DAS (CSV)**, cartão CNPJ (consultar agora, baixar ficha JSON) |
| `#/import` | Importar | CSV/QIF/OFX + conta destino (+ contrapartida p/ OFX); duplicados ignorados |
| `#/settings` | Configurações | perfil, bloco MEI (oculto no pessoal) + **Buscar dados na Receita**, usuários (admin), reset contábil (admin, mantém usuários) |

## Convenções (obrigatórias ao mexer)

- `api(path, opts)` — fetch JSON; lança `Error(msg)` com `error` do servidor.
- `fmtMinor(minor)` ↔ `parseBRL(text)` — centavos ⇄ `1.234,56`.
- `fmtDate(iso)` — `AAAA-MM-DD` → `DD/MM/AAAA` (inputs `type=date` continuam ISO).
- `esc(s)` em **todo** HTML interpolado (XSS).
- `toast(msg, kind)` para feedback; erros de API em `.error`/toast, nunca `alert`.
- Dinheiro na API sempre `*_minor`; datas na API sempre ISO.
- Downloads **não usam blob** (o webview ignora): salvar via `/api/exports/*` e abrir
  com `/api/exports/open?file=`.
- Validar JS com `node --check src/gnc_lite/web/static/js/app.js`.
