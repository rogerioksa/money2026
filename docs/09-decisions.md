# 09 — Decisões arquiteturais (ADRs)

## ADR-001 — Interface 100% pywebview (Flet e Qt removidos)
**Contexto**: coexistiam `flet_app/`, `ui/` (PySide6) e `web/`.
**Decisão**: remover `flet_app/`, `ui/`, `test_flet_screens.py`, `test_ui.py` e specs
legadas; PDF via reportlab (`services/pdf.py`).
**Consequência**: um só frontend; `exporter.write_report_pdf` delega ao reportlab.

## ADR-002 — Sessão web em memória com reidratação
**Contexto**: login se perdia entre requests (`SESSION=None` no login; `web.user`
inexistente causava 500 no `/me`).
**Decisão**: `WebSession(company, ledger, dbsession, user)`; `USER_ID` persistido no
`app.config` e reidratado em `current_session()`; `select` só limpa ao trocar de empresa.
**Consequência**: F5 mantém login; testes cobrem login→me→logout.

## ADR-003 — Marca "Money 26" sem migrar dados
**Contexto**: renomear sem perder bancos existentes.
**Decisão**: marca visível (janela, HTML, EXE `Money26.exe`) muda; `APP_NAME`,
pastas de dados e pacote `gnc_lite` permanecem.
**Consequência**: upgrade sem migração; testes legados de migração continuam válidos.

## ADR-004 — Reset preserva usuários
**Contexto**: reset antigo deletava o `.sqlite` (zerava logins, recriava `admin/admin`).
**Decisão**: `reset_company_db` deleta em ordem (baixas→títulos→partidas→
lançamentos→partes→contas), resemeia o plano e **nunca toca `users`**; sessão continua logada.
**Consequência**: coberto por `test_web_reset_keeps_users_clears_ledger`.

## ADR-005 — Contrapartida explícita na importação (IMPORTADO removido)
**Contexto**: fluxo intermediário "conta 1.9 Importado + classificar depois" não
funcionou na prática (edição de transferência falhava na UX).
**Decisão**: remover `ensure_counter_account`, `/unclassified` e `PATCH transfer`;
QIF usa categoria do arquivo, OFX usa contrapartida escolhida, CSV usa contas do arquivo.
**Consequência**: importação direta e simples; reclassificação futura deve ser
desenhada de novo do zero, não ressuscitada.

## ADR-006 — Exportações via arquivo, não download de blob
**Contexto**: anchor-download com blob morre em silêncio dentro do pywebview.
**Decisão**: endpoints salvam em `DB/exports/` e retornam `{filename, path}`;
`GET /api/exports/open?file=` abre no programa padrão (basename validado).
**Consequência**: DAS CSV e ficha CNPJ funcionam no EXE.

## ADR-007 — Minha Receita com cache e timeout (sem SLA)
**Contexto**: API pública, gratuita, sem garantia e potencialmente fora do ar.
**Decisão**: timeout 12s, erros viram mensagens amigáveis (502), resultado em
sidecar `<banco>.cnpj.json`, `stale` após 30 dias, auto-atualização silenciosa
só na tela Obrigações. Preenchimento de Config (`/fill`) nunca salva sozinho.
**Consequência**: app funciona offline com último dado conhecido.

## ADR-008 — Menus empresariais só no MEI
**Contexto**: perfil pessoal não deve ver gestão empresarial.
**Decisão**: `Empresas`, `Títulos`, `Obrigações` (menu + rotas) e relatórios MEI
só com `profile==mei`; `state.isMei` sincronizado no boot/login/salvamento.
**Consequência**: trocar o perfil atualiza o menu na hora, sem reload.

## ADR-009 — Contas cartão/cheque como natureza, não tipo novo
**Contexto**: cartão (fatura/limite) e cheque especial (limite bancário) precisam de
tratamento diferencial sem quebrar relatórios.
**Decisão**: `kind` (`normal|cartao|cheque`) + `credit_limit_minor`; cartão impõe tipo
passivo, cheque impõe ativo; relatórios existentes inalterados; migração leve em
`init_db` para bancos antigos.
**Consequência**: limite/usado/disponível em API e telas; DRE/balanço intactos.
