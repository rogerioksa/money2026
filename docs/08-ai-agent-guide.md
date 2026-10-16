# 08 — Guia do agente IA (qualquer modelo)

Como trabalhar neste repositório sem quebrar nada. Leia `00`→`07` conforme a tarefa.

## Sessão padrão de trabalho

1. **Entenda antes de mexer**: `grep`/`glob`/`read` nos arquivos envolvidos.
   Nunca assuma nomes de campo — confira em `models.py`, `repository.py` e no teste.
2. **Planeje em todos**: crie/atualize a lista de tarefas e marque progresso real
   (só marque `completed` após verificação executada).
3. **Mude o mínimo**: prefira `edit` com contexto pequeno; nunca crie arquivo novo
   sem necessidade; nunca use `bash` para ler/editar arquivos (há ferramentas próprias).
4. **Verifique executando** (ordem de `06-build-release.md`):
   `pytest -q` → `ruff check src tests` → `node --check app.js` →
   smoke da API via `test_client` → rebuild + smoke do EXE quando pedido.
5. **Resuma com fatos**: arquivos:linhas, nº de testes, resultado do smoke.

## Mapa mental por tipo de tarefa

| Pedido | Mexer em | Testar em |
|---|---|---|
| Nova tela/UX | `web/*` (+ endpoint se faltar dado) | `node --check`, smoke visual no EXE |
| Novo endpoint | `api/*` + registrar em 2 lugares | `tests/test_web_api.py` |
| Regra contábil | `domain/` + `services/` | `test_*` correspondente |
| Nova coluna | `models.py` + `session._migrate` + `repository` | `test_db.py` (caso legado) |
| Obrigação/CNPJ | `services/obligations.py|cnpj.py` + `api/*` + `app.js` | `test_obligations.py` + `test_web_api.py` |
| Login/permissão | `app_webview.py` + `api/auth_bp|users_bp` | fluxo login→me→logout em `test_web_api.py` |
| Build/EXE | `webview_pack.spec` | rebuild + smoke `RUNNING-OK` |

## Proibições (com motivo)

- ❌ Reintroduzir Flet/Qt/`flet_app`/`ui` — removidos por decisão (ver `09-decisions.md`).
- ❌ `unlink()` em banco do usuário; reset que toque `users`.
- ❌ `float` para dinheiro; datas não-ISO na API; `user.display` (é `display_name`).
- ❌ Download por blob no frontend (webview ignora); usar `/api/exports/*`.
- ❌ Renomear `APP_NAME`, pastas de dados ou pacote `gnc_lite` (perde dados/instalação).
- ❌ Commit/push/PR sem pedido explícito.
- ❌ `Select-Object -First` para "economizar" saída do pytest — o resumo fica no fim
  (`-Last`); saída de build longa: resumir, não truncar com comandos de corte.

## Comunicação

- Respostas curtas, técnicas, sem bajulação. Se algo pedido quebra invariante,
  discordar com o motivo e oferecer alternativa.
- Ao final de mudança funcional: o que mudou (arquivos), como foi verificado
  (testes/lint/smoke) e o que o usuário precisa fazer (ex.: abrir `Money26.exe`).
- Dúvida travando a solução → perguntar com opções concretas (usar a ferramenta
  de perguntas quando disponível).
