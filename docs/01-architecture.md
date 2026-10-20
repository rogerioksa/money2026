# 01 — Arquitetura

## Camadas (dependência só para baixo)

```
web/ (SPA: base.html + style.css + app.js)
  │  HTTP JSON 127.0.0.1
  ▼
api/ (blueprints Flask) ──► services/ (budget, reports, importer, reconcile)
  │                              │
  │                              ▼
  │                        db/repository.py ──► db/models.py (SQLite)
  ▼
app.py (create_app() + sessão por request + launcher pywebview)
```

- `domain/` é puro (sem SQLAlchemy/Flask): `Account`, `Transaction`, `Split`,
  `BudgetEntry`, helpers de `Money`.
- `services/` orquestra domínio + repositório.
- `api/` é fina: parseia payload, chama serviço/repositório, serializa.

## Ciclo de request

1. `create_app()` cria o engine SQLite e roda `init_db` (create_all + `_migrate` + seed).
2. Cada request pega uma sessão via `g` (`app.extensions["get_repo"]`).
3. `teardown_appcontext` faz `commit()` no sucesso e `rollback()` em erro, e fecha a sessão.

## Launcher pywebview

`run_webview()` escolhe porta livre em `127.0.0.1`, sobe o Flask em thread daemon
e abre `webview.create_window("Money 99", url)`. Recursos `templates/` e `static/`
são resolvidos via `_resource_base()` (usa `sys._MEIPASS` quando congelado).

## Invariantes

1. **Partidas dobradas simplificadas**: `Transaction.validate()` — valor ≠ 0;
   transferência sem categoria/splits; splits somam o valor.
2. **Dinheiro em centavos** (int); parsing pt-BR só nas bordas.
3. **Datas ISO na API**; exibição BR só no frontend.
4. **Sinal**: `amount` assinado do ponto de vista de `account_id`; a conta destino
   de uma transferência recebe `-amount`.
5. Filtro de fim de mês usa a string `AAAA-MM-31`.
