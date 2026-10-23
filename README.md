# Money 2026

Gerenciador financeiro pessoal em Python, inspirado no Microsoft Money:
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
node --check "src\money99\web\static\js\app.js"
```

## Garantia operacional e UX

O projeto foi refinado para uso desktop com foco em produtividade e segurança:

- atalhos de teclado e foco automático para cadastro e edição de registros
- confirmação em ações destrutivas e feedback visual de carregamento
- ajustes de contraste e visibilidade para navegação acessível
- páginas de impressão com margens reduzidas para relatório e MEI
- empacotamento com PyInstaller validado por smoke test do executável gerado

## Documentação

Guias em `docs/` (visão geral, arquitetura, API, banco, build). Em caso de conflito
entre documentação e comportamento, o código e os testes são a fonte final de verdade.
