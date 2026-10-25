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

1. Padrão (ardósia/azul-aço): fundo `#f2f4f8`, acento `#2f5fa8`,
   header `#17324d`, linha alternada `#f7f0dd`.
2. Midnight: fundo `#0b1220`, acento `#7aa2f7`, header `#141b2d`.
3. Sunset: fundo `#fbf6f1`, acento `#b86b3d`, header `#8f4e2f`.
4. Deep Ocean: fundo `#eaf7f8`, acento `#0e7c74`, header `#0f6b63`.

Esses temas ficam disponíveis por meio do atributo `data-theme` no `<body>` e são persistidos no `localStorage` sob a chave `money99-theme`. A escala `brand` do Tailwind e o `box-shadow` acompanham a paleta do tema padrão.

## Skills consultadas

- `design-better`
- `tailwind-design-system`
- `ux-writing`

As mudanças foram orientadas por princípios de hierarquia visual, contrastes, feedback de interação e clareza de microcopy, preservando o comportamento funcional do sistema.
