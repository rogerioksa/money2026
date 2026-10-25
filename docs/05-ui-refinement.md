# Refinamento visual do extrato e temas

## Resumo

Ajustamos o layout visual do extrato para melhorar a leitura e a consistência do sistema financeiro, mantendo a estrutura já usada pelo app e preservando a experiência do usuário.

## Alterações aplicadas

- Reorganização do extrato por dia em blocos de cartão, mantendo contexto financeiro por período.
- Ajuste das colunas para largura fixa e alinhamento horizontal entre cabeçalho e dados.
- Aplicação de listras alternadas para facilitar a leitura das linhas do extrato.
- Destaque visual do segundo cartão com azul claro e de linhas alternadas com amarelo suave.
- Atualização dos tokens de tema para uma paleta mais premium e consistente em todos os esquemas disponíveis.
- Ajuste de contraste e bordas para manter visual limpo, legível e uniforme.

## Temas

Os esquemas de cor foram revisados para manter uma estética premium em todos os temas:

- padrão
- midnight
- sunset
- deep-ocean

## Validação

As alterações visuais foram validadas com:

- `npm run build:css`
- `node --check "src\money99\web\static\js\app.js"`

Esses comandos foram executados com sucesso após o refinamento.
