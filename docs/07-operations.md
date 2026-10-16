# 07 — Operação, dados e troubleshooting

## Mapa de dados (máquina do usuário)

| O quê | Onde | Observação |
|---|---|---|
| Bancos | `<pasta do exe>/DB/*.sqlite` (dev: `<cwd>/DB/`) | fallback `%APPDATA%/GnuCashLite/` |
| Empresas | `DB/empresas.json` | `{id, name, db_path}`; migração automática do legado |
| Config/perfil/MEI | `%APPDATA%/GnuCashLite/config.json` | **global** (não é por empresa) |
| Cumprimento DAS/RMR/DASN | `<banco>.obrigacoes.json` | `{key: {done, at}}`, ex. `das:2026-04` |
| Cache CNPJ | `<banco>.cnpj.json` | `{cnpj, checked_at, result}`; obsoleto >30d |
| Exportações | `DB/exports/` | `DAS_<ano>_situacao.csv`, `CNPJ_<n>_ficha.json` |

Backup = copiar `DB/` + `%APPDATA%/GnuCashLite/config.json`.

## Troubleshooting

| Sintoma | Causa provável | Ação |
|---|---|---|
| Login "não funciona" / volta p/ login | `WebSession.user` não reidratado; `select` limpando `USER_ID` | ver `current_session()`/`_resolve_user`; `select` só limpa ao trocar de empresa |
| `/me` 500 | acesso a atributo inexistente (`display` vs `display_name`) | usar `getattr` defensivo |
| Tela congela no "Nenhuma empresa" | JS chamando função inexistente | checar console; `route()` cobre `!companies` → `renderCompanies` |
| Clique em baixar não faz nada | blob download no webview | usar fluxo `/api/exports/*` (salvar+abrir), nunca blob |
| Menu MEI visível no pessoal | `state.isMei` dessincronizado | `syncProfile()` no boot/login; `route()` re-aplica após salvar perfil |
| Import QIF falha | categoria `L` fora do plano | mapear código ou escolher contrapartida válida |
| PDF vazio/erro | reportlab ausente no venv | `pip install -e .` (reportlab é dependência) |
| CNPJ 502/timeout | Minha Receita fora ou sem internet | mensagem já amigável; cache mantém última situação |
| Coluna nova não existe em banco antigo | migração ausente | adicionar bloco em `session._migrate` + teste em `test_db.py` |
| EXE abre e fecha | erro no boot (porta/template) | rodar `python -m gnc_lite.__main_webview__` no terminal p/ ver traceback |

## FAQ de manutenção

- **Adicionar endpoint?** Criar/editar blueprint em `api/`, registrar em
  `api/__init__.py` + `app_webview.py`, cobrir em `test_web_api.py`.
- **Adicionar tela?** Link em `base.html` (+`data-mei` se empresarial), rota em
  `route()`/`MEI_ROUTES`, `renderX()` em `app.js`, seguir convenções de `05-frontend.md`.
- **Adicionar coluna no banco?** Model + `_migrate` + `_to_domain_*` + teste legado.
- **Mudar regra contábil?** `domain/` + `services/` + testes; frontend só exibe.
- **Reset apagou usuários?** Não deve: `reset_company_db` nunca toca `users`
  (regressão coberta por `test_web_reset_keeps_users_clears_ledger`).
