# 01 — Arquitetura

## Camadas (dependência só para baixo)

```
web/ (SPA: base.html + style.css + app.js)
  │  HTTP JSON 127.0.0.1
  ▼
api/ (blueprints Flask) ── usa ──► services/ (ledger, billing, reports, mei, ...)
  │                                    │
  │                                    ▼
  │                              db/repository.py ──► db/models.py (SQLite)
  ▼
app_webview.py (WebSession por empresa + usuário logado)
```

- `domain/` é puro (sem SQLAlchemy, sem Flask): `Account`, `Money`, `Transaction`,
  `Split`, `Invoice`, `Party`, `User`, `Role`. Qualquer agente pode confiar que
  regra contábil vive aqui ou em `services/`, nunca no frontend.
- `services/` orquestra domínio + repositório. Ex.: `BillingService` emite títulos
  **e** posta os lançamentos correspondentes (dupla entrada garantida no serviço).
- `api/` é fina: parseia payload, chama serviço, serializa, commita (`web.dbsession.commit()`).
  **Todo endpoint que escreve deve commitar; em erro, `rollback()`.**

## Runtime: Flask + pywebview (`app_webview.py`)

1. `run_webview()` escolhe porta livre em `127.0.0.1`, sobe o Flask em thread daemon
   (`threaded=False`), espera a porta responder e abre `webview.create_window("Money 26", url)`.
2. `create_app()` configura `static_folder`/`template_folder` via `_resource_base()`
   (usa `sys._MEIPASS` quando congelado — é assim que o EXE encontra `web/`).
3. `GET /` serve `base.html`; todo o resto é JSON em `/api/*`.

## WebSession e autenticação

```python
@dataclass
class WebSession:
    company: Company      # empresa ativa
    ledger: Ledger        # fachada contábil (repo dentro)
    dbsession: Session    # sessão SQLAlchemy aberta
    user: User | None     # logado (None = anônimo)
```

- `app.config` guarda `COMPANY_ID`, `SESSION`, `USER_ID`.
- `current_session()` reabre o livro ao trocar de empresa e **reidrata o usuário**
  via `USER_ID` (`_resolve_user`). Comportamento testado em `test_web_api.py`.
- `POST /api/companies/select` só limpa `SESSION`/`USER_ID` **quando a empresa muda**
  (mesma empresa preserva o login — importante para o F5 da SPA).
- `POST /api/auth/login` autentica via `AuthService` e anexa `web.user`
  (não zera a sessão). `GET /api/auth/me` reflete o estado. `POST /logout` limpa.
- `WebSession.can_write` = `True` sem login (bootstrap/testes) ou `user.role.can_write`;
  `is_admin` análogo. Endpoints de escrita exigem `can_write`; admin exige
  `user.role.is_admin` (usuários, reset).

## Invariantes que um agente deve preservar

1. **Partidas dobradas**: `Transaction.validate()` exige soma zero; nunca persistir
   lançamento desbalanceado.
2. **Dinheiro em centavos** (`Money.minor_units: int`); parsing pt-BR só nas bordas
   (API recebe `minor_units`; frontend converte com `parseBRL`/`fmtMinor`).
3. **Datas na API em ISO** (`AAAA-MM-DD`); exibição BR (`DD/MM/AAAA`) só no frontend
   (`fmtDate`).
4. **`display_name`** é o campo de exibição do usuário (não existe `display`).
5. **`Account.parent`** é objeto (não `parent_id`); acesso via `ledger.repo.*`.
6. **Sem Flet/Qt**: o projeto é 100% pywebview. Não reintroduzir `import flet`,
   `PySide6` ou `flet_app/`/`ui/` (removidos). PDF usa **reportlab** (`services/pdf.py`).
7. **Compatibilidade de dados**: `APP_NAME = "GnuCashLite"` e pastas de dados NÃO mudam
   (renomear perde bancos existentes). Marca visível é "Money 26"; pacote é `gnc_lite`.
