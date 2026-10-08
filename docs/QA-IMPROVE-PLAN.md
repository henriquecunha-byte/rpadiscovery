# btime RPA Docs — plano de refinamento

Data: 08/10/2026. Escopo: aplicação local existente em FastAPI, HTML, CSS e JavaScript.

## Objetivo e critérios de entrega

Preparar uma versão candidata ao uso diário no pós-discovery de RPA: receber gravações, entender o pedido, acompanhar a análise e revisar documentação e vídeos editados. A identidade vem dos pacotes oficiais de design e motion fornecidos pelo usuário. O histórico, os dados locais e as funcionalidades estabelecidas devem ser preservados.

## Sequência de trabalho

1. **Diagnóstico:** examinar interface, contratos da API, fila, uploads, processamento, documentos e testes existentes. Registrar riscos concretos.
2. **Estrutura de produto:** separar nova análise, histórico e integração; manter acompanhamento e entrega acessíveis por trabalho.
3. **Nova análise:** pilha incremental de vídeos/pastas/ZIPs; remoção individual; validação antes do envio; contexto por pedido; recuperação do rascunho textual; autorização explícita e feedback de upload; impedir submissão duplicada.
4. **Histórico e acompanhamento:** busca e filtro; estados vazio/carregando/erro; detalhes do pedido sempre acessíveis; progresso e estimativa honesta; cancelar/retomar; limpeza com confirmação; atualização sem interromper reprodução nem roubar foco.
5. **Entrega:** resumo do resultado; documentos estruturados por formato; preview individual por fonte; roteiro de cortes e ZIP; acesso aos avisos/limites da análise; reaproveitar pedido.
6. **Confiabilidade:** corrigir falhas comprovadas de validação, ZIP, fila, recuperação de interrupção, resultados legados e processamento. Manter seleção contextual orientada pela fala, sem porcentagem-alvo de cortes.
7. **Identidade e acessibilidade:** SVG oficial, Branding 350/500/600, violeta/noite/branco frio, contraste calculado, foco visível, dialogs reais, teclado, alvos de toque, estados completos, movimento reduzido e responsividade.
8. **Aceite:** testes de regressão com armazenamento isolado; vídeos sintéticos para previews/ZIP; QA de navegador em 375/768/1024/1440 px, erros, teclado, reduzido, persistência e reprodução; registro de resultados e pendências reais.

## Direção visual e de movimento

Painel operacional claro sobre branco frio, navegação noite e ações violeta. Tipografia Branding com títulos legíveis, respiro de 8/16/24/32 px e superfícies estáveis para trabalho. Assets oficiais preservam geometria e proporção. A expressão de marca fica restrita a uma área de abertura, com conteúdo operacional predominante.

Interações de 160 ms e troca de painéis de 320 ms, entrada por deslocamento curto e opacidade, sem overshoot. Rolagem natural. APIs nativas atendem o escopo; as famílias GSAP e Three.js orientam a revisão, sem exigir novo runtime 3D. A autorização do usuário para executar o plano e o design system fornecido definem a direção; não há rodada adicional de aprovação de tese visual.

## Limites de uma versão local

Publicação corporativa depende de destino de hospedagem, URL do repositório vinculado ao Lovable, autenticação de equipe, isolamento dos dados por usuário e configuração OAuth de produção. Não migrar o repositório nem publicar nesta revisão. Não declarar qualidade semântica de IA validada a partir de testes simulados; separar teste de infraestrutura de revisão de uma reunião real.

## Achados iniciais

- A interface não utiliza a identidade Btime atual nem a fonte e assinatura oficiais.
- Selecionar fontes de outro tipo pode apagar a seleção anterior sem aviso.
- Submissão não bloqueia duplo clique e não mostra progresso de transferência.
- Histórico e eventos usam texto externo em HTML interpolado.
- Atualização periódica não trata adequadamente desconexão ou respostas fora de ordem.
- Modal do Drive não implementa o comportamento acessível de um dialog.
- Entregáveis existentes, como Word e requisitos de RPA, ficam pouco visíveis.
- Validação multipart, ZIP e recuperação de fila precisam de testes de regressão.

Execução concluída como versão candidata local. Mudanças, evidências e limitações verificadas estão em [QA-REPORT.md](QA-REPORT.md).
