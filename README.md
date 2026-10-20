# Money 99

Gerenciador financeiro pessoal em Python, inspirado no Microsoft Money 99:
contas, transações com categorias, orçamentos, relatórios e importação QIF/OFX.

Interface web local (Flask + pywebview) empacotada em `.exe` único (PyInstaller).
Dados em SQLite, dinheiro em centavos (inteiros), interface pt-BR / BRL.

## Desenvolvimento

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,build]"
money99            # abre janela pywebview
pytest             # testes
ruff check src tests
```

## Documentação

Guias em `docs/` (visão geral, arquitetura, API, banco, build).
