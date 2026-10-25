# Design do sistema

Este projeto usa uma abordagem de design baseada em tokens semânticos e temas leves para facilitar manutenção visual e melhor experiência de uso.

## Tokens principais

- fundo: `--money-bg`
- texto principal: `--money-fg`
- destaque: `--money-accent`
- destaque suave: `--money-accent-soft`
- borda: `--money-border`
- superfície: `--money-surface`
- cabeçalho: `--money-header`
- contraste do cabeçalho: `--money-header-contrast`
- hover de linha: `--money-row-hover`
- fundo de campos: `--money-field-bg`

## Temas atuais

1. Floresta (padrão)
2. Midnight
3. Sunset
4. Deep Ocean

Esses temas ficam disponíveis por meio do atributo `data-theme` no `<body>` e são persistidos no `localStorage` sob a chave `money99-theme`.

## Skills consultadas

- `design-better`
- `tailwind-design-system`
- `ux-writing`

As mudanças foram orientadas por princípios de hierarquia visual, contrastes, feedback de interação e clareza de microcopy, preservando o comportamento funcional do sistema.
