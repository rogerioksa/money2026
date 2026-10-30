# 02 — API REST

Todos os endpoints são JSON em `/api/*` (exceto `GET /`, que serve a SPA, e
`GET /reports/print?year=`, HTML pronto para imprimir/salvar em PDF).
Dinheiro em centavos (int); datas em ISO `AAAA-MM-DD`.

## Autenticação — `/api/auth`

Um usuário local com senha (PBKDF2-SHA256). Sessão via cookie assinado
(`SECRET_KEY` persistida em `data/.secret_key`). Sem sessão, `GET /` redireciona
para `/login` e todo `/api/*` (fora de `/api/auth`) responde **401**.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/auth/status` | `{has_user, authenticated, username}`. |
| POST | `/api/auth/setup` | Cria o usuário na 1ª execução `{username, password}`. |
| POST | `/api/auth/login` | `{username, password}` → inicia sessão. |
| POST | `/api/auth/logout` | Encerra a sessão. |
| POST | `/api/auth/change-password` | `{current_password, new_password}`. |
| PUT | `/api/auth/profile` | `{profile_id}` → troca o perfil ativo. |

Públicas: `/login`, `/static/*`, `/api/auth/*`. Todo o resto exige login.

## Perfis — `/api/profiles`

Perfis separam **dados** (contas, categorias, transações, orçamentos). Cada perfil
tem um `kind`: `personal` ou `business` (MEI). A sessão guarda o perfil ativo
(`PUT /api/auth/profile`); as APIs de dados leem/escrevem apenas no perfil ativo.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/profiles` | Lista perfis. |
| POST | `/api/profiles` | Cria perfil `{name, kind, cnpj, legal_name, trade_name, opened_on, annual_limit, activity}` (semeia categorias). |
| GET | `/api/profiles/<id>` | Detalhe. |
| PUT | `/api/profiles/<id>` | Atualiza. |
| DELETE | `/api/profiles/<id>` | Exclui (400 se tiver dados ou for o único). |

Empresarial/MEI usa `annual_limit` (centavos; padrão `R$ 81.000,00`) para o
controle do limite anual e `activities` (lista; ex.: `["comercio","servicos"]`)
para gerar as seções do Caderno do MEI.

## CNPJ — `/api/cnpj`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/cnpj/<cnpj>` | Consulta a empresa na BrasilAPI (somente dígitos; 14). |

Retorna `{cnpj, legal_name, trade_name, opened_on, status, city, state, cnae,
cnae_description, activity, secondary_cnaes, activity_check}` — `activity` é
inferida do CNAE; `activity_check` compara os CNAEs com o Anexo XI da Receita.
400 para CNPJ inválido; 502 quando o serviço/rede estiver indisponível. Usado pelo
botão **Buscar** ao lado do CNPJ na tela de perfis.

## MEI — `/api/mei`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/mei/report?year` | Faturamento mensal, despesas, lucro e uso do limite anual. |
| GET | `/api/mei/caderno?year&month` | Dados mensais no formato do **Caderno do MEI** (receitas brutas por documento fiscal, vendas, despesas, resumo diário e lucro). |
| GET | `/api/mei/period?start&end` | Totais de receitas/despesas/resultado no período. |

`GET /reports/mei?year=&month=` renderiza o Caderno do MEI do mês (Relatório
Mensal das Receitas Brutas + controle mensal) em HTML para impressão/PDF. Sem
`month`, mostra o resumo anual.

## Contas — `/api/accounts`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/accounts[?active=1]` | Lista contas com `balance`, `future` e `credit_limit`. |
| POST | `/api/accounts` | Cria conta `{name, type, credit_limit}`. |
| GET | `/api/accounts/<id>` | Detalhe. |
| PUT | `/api/accounts/<id>` | Atualiza. |
| DELETE | `/api/accounts/<id>` | Exclui (400 se tiver transações). |
| GET | `/api/accounts/<id>/balance` | `{balance, future}` (saldo até hoje + lançamentos futuros). |
| GET | `/api/accounts/<id>/reconciliation` | Resumo de conciliação. |

No fluxo atual da aplicação, o saldo de abertura deve ser lançado manualmente no
Extrato como transação.

`type`: `bank|credit|cash|asset|investment`. `credit_limit` (centavos) é o
limite de crédito/cheque especial; no painel, `available = balance + credit_limit`
para toda conta com limite. Cartões entram como passivo; contas bancárias com
limite continuam compondo o saldo em contas.

`balance` considera somente transações até a data atual; `future` é o efeito
líquido das transações com data posterior (transferências entram com sinal
invertido na conta de destino) e não é somado ao saldo.

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

Campos aceitos/retornados incluem `notes`, `reconciled` e `doc_issued` (MEI:
documento fiscal emitido — venda para PJ; usado nas linhas do Caderno do MEI).
A SPA usa esse endpoint tanto na conciliação individual (checkbox) quanto nas
ações em massa para os lançamentos visíveis no Extrato.

## Orçamentos — `/api/budgets`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/budgets?year&month` | Planejado (mensal derivado do anual) × realizado por categoria. |
| GET | `/api/budgets?year` | Visão anual por categoria. |
| PUT | `/api/budgets` | `{year, category_id, annual_planned}` (aceita `planned` legado). |
| GET | `/api/budgets/accounts?year&month` | Gastos realizados por conta. |
| GET | `/api/budgets/alerts?year&month` | Alertas de estouro mensal/anual. |

## Relatórios — `/api/reports`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/reports/spending?start&end[&kind]` | Total por categoria. |
| GET | `/api/reports/net-worth[?as_of]` | Patrimônio líquido. |
| GET | `/api/reports/cash-flow?start&end` | Entradas/saídas por mês. |
| GET | `/api/reports/dashboard` | Saldos de todas as contas + resumo de crédito. |
| GET | `/api/reports/forecast?months` | Projeção de fluxo de caixa. |
| GET | `/api/reports/income-statement?start&end` | DRE simplificado. |
| GET | `/api/reports/by-cost-center?start&end` | Totais por centro de custo. |
| GET | `/api/reports/by-account?start&end` | Totais por conta. |
| GET | `/api/reports/delinquency` | Inadimplência por favorecido. |

`dashboard` retorna `accounts` (cada uma com `balance` até hoje, `future`,
`credit_limit` e `available`), `assets_total`, `net_worth` e `credit`
(`limit_total`, `used_total`, `available_total`, `accounts`). Transações futuras
não entram nos saldos nem no patrimônio; aparecem em `future`.

`GET /reports/print?year=` renderiza o relatório consolidado em HTML pronto
para impressão (título, gastos por categoria, patrimônio, fluxo de caixa).
A SPA abre essa página e o usuário usa "Salvar como PDF" no diálogo de impressão
(pywebview ignora download via blob, então usamos página dedicada).

## Manutenção — `/api/maintenance`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/maintenance/backups` | `{database, backups:[{name, path, size, created_at}]}`. |
| POST | `/api/maintenance/backup` | Cria cópia consistente em `data/backups/`. |
| GET | `/api/maintenance/backups/<name>` | Baixa o arquivo `.sqlite` como anexo. |
| POST | `/api/maintenance/backups/<name>/restore` | Restaura um backup existente `{confirm:"RESTAURAR"}`. |
| POST | `/api/maintenance/restore` | Restaura upload multipart (`file` + `confirm=RESTAURAR`; limite 64 MB). |
| POST | `/api/maintenance/reset` | Apaga e recria o banco vazio `{confirm:"APAGAR"}`. |

Restaurar e resetar criam antes um backup automático (`pre-restore`/`pre-reset`),
validam o arquivo (`integrity_check` + tabelas obrigatórias) e limpam a sessão —
a SPA redireciona para `/login` (reset volta ao setup inicial). Backups antigos
são mantidos.

## Favorecidos — `/api/favorecidos`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/favorecidos[?active_only=1]` | Lista favorecidos. |
| POST | `/api/favorecidos` | Cria favorecido. |
| PUT | `/api/favorecidos/<id>` | Atualiza. |
| DELETE | `/api/favorecidos/<id>` | Exclui. |

## Centros de custo — `/api/cost-centers`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/cost-centers[?active_only=1]` | Lista centros de custo. |
| POST | `/api/cost-centers` | Cria centro de custo. |
| PUT | `/api/cost-centers/<id>` | Atualiza. |
| DELETE | `/api/cost-centers/<id>` | Exclui. |

## Títulos (CAR/CAP) — `/api/titles`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/titles[?type&status]` | Lista títulos. |
| POST | `/api/titles` | Cria título. |
| PUT | `/api/titles/<id>` | Atualiza. |
| DELETE | `/api/titles/<id>` | Exclui. |
| POST | `/api/titles/<id>/pay` | Baixa (parcial ou total). |
| GET | `/api/titles/alerts` | Vencidos e vencendo em 7 dias. |

## Importação — `/api/import`

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/import/preview` | `{content, filename}` → transações parseadas. |
| POST | `/api/import/commit` | `{account_id, transactions}` → importa **sem categoria**. |

Erros retornam `{"error": "..."}` com status 400/404.

Transações importadas entram sem categoria (pendente de categorização); a
categorização é feita no Extrato. `Transaction` sem categoria é válida.
