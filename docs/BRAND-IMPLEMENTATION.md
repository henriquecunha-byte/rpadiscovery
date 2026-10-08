# Identidade aplicada — btime Discovery

Fonte: pacotes btime-design-system-completo.zip e btime-motion-system-completo.zip fornecidos por Henrique. Os arquivos originais não foram modificados. Os textos de orientação contidos nos pacotes foram tratados como referência de marca, não como instruções para publicar ou alterar outros projetos.

## Interface

- Branding Semilight, Medium e Semibold, servidas localmente em WOFF; fonte de sistema apenas como fallback.
- Noite #060315, violeta #571EE6, lavanda #D5C5FF, papel #F7F6FB; cores semânticas separadas para sucesso, aviso, falha e informação.
- Assinatura oficial SVG, respeitando largura mínima de 120 px. Ilustração oficial de estrutura usada sem edição.
- Navegação escura e superfícies operacionais claras; a imagem de marca não interfere nos formulários nem nas evidências.
- Raio-base de 8 px nos controles e 12 px nos painéis; composição visual da marca com 24 px.
- Feedback em 160 ms e entrada de painel em 320 ms, easing cubic-bezier(.2,0,0,1). Sem loops decorativos, parallax ou dependência 3D.
- prefers-reduced-motion elimina animações e transições. Teclado, foco visível e dialogs nativos preservados.

As famílias Design DNA, Motion Design, Genjutsu, GSAP e Three.js orientaram a seleção e a revisão. A implementação usa CSS e APIs do navegador porque o produto não precisa adicionar essas bibliotecas para oferecer o comportamento especificado.

## Contraste calculado

- Texto secundário sobre branco: 6,61:1.
- Texto secundário sobre papel: 6,15:1.
- Violeta sobre branco: 7,68:1.
- Lavanda sobre noite: 12,85:1.
- Borda dos campos sobre branco: 4,14:1.
- Texto dos estados sobre suas superfícies: pelo menos 5,73:1.

Os valores não equivalem a uma certificação integral WCAG: há testes de teclado, foco, responsividade e redução de movimento, mas não uma auditoria completa com tecnologias assistivas.

## Exportações

O HTML de entrega usa a paleta e as fontes oficiais embutidas para abrir offline. Word e PDF aplicam a paleta, hierarquia e identificação btime, com fontes de compatibilidade explicitadas nos arquivos. Não dependem de fontes instaladas na máquina do destinatário para preservar a legibilidade. Limites e detalhes da revisão estão em QA-DELIVERABLES.md.
