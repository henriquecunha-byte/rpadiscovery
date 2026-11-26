# Discovery — pedidos do Hiago para implementação no Lovable

Preparado em: 29/10/2026. Referência: reunião “Ferramenta de Discovery”, de 14/10/2026.

## Instrução para o Lovable

Revise o aplicativo Discovery existente e implemente o que estiver faltando para atender aos requisitos abaixo. O objetivo principal é transformar gravações de discovery em documentação operacional com **prints das telas e descrição do passo a passo**, pronta para revisar e compartilhar com o cliente.

**Preserve a API, o provedor de IA e o banco de dados que já estão configurados neste projeto Lovable.** Reutilize autenticação, permissões, armazenamento e serviços existentes. Não substitua o backend pelo projeto Python de referência, não migre o banco, não crie um novo projeto Cloud e não troque chaves ou credenciais.

É permitido ajustar a lógica de geração e exportação usando os serviços atuais. Se algum requisito exigir mudança de esquema, infraestrutura ou contrato incompatível com a API atual, explique a dependência e peça uma decisão antes dessa mudança. Não marque uma entrega como pronta apenas porque a tela foi implementada.

## 1. Pedidos identificados na reunião

Os horários são aproximados, contados desde o início da gravação. Este documento resume o feedback do trecho de discussão com Hiago; não é uma transcrição literal. A transcrição usada como apoio é automática e não identifica os locutores de forma confiável.

| Prioridade | Pedido / feedback | Referência aproximada |
| --- | --- | --- |
| P0 | Mostrar o documento gerado com os prints, para avaliar a entrega concreta. | 12:46–12:50 |
| P0 | Priorizar prints de tela como principal valor da documentação de discovery de RPA. Eles devem servir de evidência complementar à gravação para documentar com o cliente. | 13:32–14:00 |
| P0 | Incluir os prints no PDF. Durante a demonstração, foi constatado que o PDF não continha essas imagens. | 14:17–14:29 |
| P0 | Entregar um gerador de passo a passo **tela a tela**, explicando cada etapa do processo. Um fluxo operacional genérico, sozinho, não atende a esse pedido. | 15:18–15:59 |
| P1 | Manter os recortes de vídeo como complemento útil, com prioridade para as evidências em imagem na documentação. | 13:38–13:48 |
| Futuro | Avaliar a incorporação da solução à ferramenta interna mencionada na reunião. Nome, integração e responsáveis devem ser confirmados com a equipe antes de implementar. | 15:09–15:18 |

## 2. Como transformar esses pedidos em funcionalidades

Os itens desta seção são critérios propostos para implementar e verificar o feedback. Não são falas literais nem novos pedidos atribuídos ao Hiago.

### 2.1. Documento com evidências visuais

- Selecionar imagens reais da gravação que mostrem as telas e os estados relevantes do processo demonstrado.
- Relacionar cada imagem à etapa que ela comprova, com legenda e descrição do que acontece naquele ponto.
- Priorizar o conteúdo compartilhado em tela. Evitar usar rostos dos participantes, telas de espera ou imagens repetidas como evidência de uma ação que não aparece.
- Selecionar frames legíveis, evitando capturas no meio de transições quando houver uma opção estável.
- Usar o áudio para compreender a ação e o contexto; usar a imagem para evidenciar o que está visível. Não inferir um processo inteiro apenas pelos frames.
- Diferenciar o que foi demonstrado em tela do que foi apenas explicado verbalmente.
- Quando uma ação não tiver evidência visual, registrar essa limitação. Não inventar telas, campos, cliques ou resultados.

### 2.2. Passo a passo tela a tela

Organizar o procedimento em etapas numeradas, na sequência necessária para entender a execução. Para cada etapa, apresentar, quando houver informação na gravação:

1. **Título da ação:** o que a pessoa faz.
2. **Sistema e tela:** onde a ação acontece.
3. **Descrição:** ação executada e contexto necessário para compreendê-la.
4. **Campos ou informações utilizadas:** apenas os identificados na gravação.
5. **Evidência visual:** print correspondente, com legenda.
6. **Resultado observado:** o que muda depois da ação.
7. **Regras, exceções ou pendências:** somente quando explicadas ou demonstradas; dúvidas devem ficar identificadas como pontos a validar.

Esses itens organizam a documentação; não devem virar campos obrigatórios adicionais para quem está enviando a gravação. Se uma informação não existir na fonte, não a preencher por suposição.

Um resumo executivo e um fluxograma podem acompanhar o procedimento, mas não substituem o detalhamento tela a tela.

### 2.3. PDF e demais formatos existentes

- O **PDF deve conter as imagens incorporadas no próprio arquivo**, junto das etapas e legendas correspondentes.
- O documento precisa continuar compreensível depois de baixado e aberto sem conexão. Um link para o vídeo ou uma imagem dependente de URL temporária não atende sozinho ao requisito.
- Preservar a proporção e a legibilidade das capturas, com paginação que mantenha clara a associação entre etapa, descrição e imagem.
- Manter no PDF as evidências selecionadas para a documentação exibida no app. Não apresentar uma versão ilustrada na tela e exportar somente o texto.
- Se o aplicativo já oferece Word/DOCX, manter a mesma correspondência entre texto e imagens nesse formato. Esse é um critério de consistência da entrega existente; o problema explicitamente observado na reunião foi o PDF.
- Preservar as outras exportações já disponíveis. Não criar novos formatos como condição para concluir esta correção.

### 2.4. Vídeos como complemento

- Preservar os previews e cortes existentes, sem exigir que o cliente reproduza um vídeo para entender o documento.
- Quando já houver referências temporais, mantê-las como apoio à rastreabilidade das evidências.
- Não introduzir nova hospedagem de vídeo ou mudança de armazenamento para atender a este pedido.

## 3. Preservar o fluxo e o escopo atuais

Na apresentação, Henrique demonstrou categorização do pedido, público, checklist de entregáveis, sistemas utilizados, guia e revisão. Esses elementos são contexto do produto apresentado, não pedidos novos atribuídos ao Hiago.

- Manter os perfis gerais de documentação, além de Processo / RPA. O detalhamento de automação não deve ser imposto a reunião, treinamento, entrevista ou pesquisa.
- Respeitar objetivo, público e entregáveis selecionados no pedido.
- Quando o usuário selecionar documentação tela a tela / prints, essa escolha precisa orientar a geração e aparecer na entrega, não somente no resumo do formulário.
- Preservar edições manuais do guia e escolhas do checklist.
- Manter documentos e evidências vinculados ao usuário autorizado, usando as permissões existentes.

## 4. Fora do escopo desta implementação

- Trocar API, modelo/provedor configurado, chaves, banco, autenticação ou infraestrutura do projeto atual.
- Reaproveitar tokens de outros projetos, como foi cogitado na discussão técnica da reunião.
- Migrar arquivos para Drive ou redesenhar a política de armazenamento.
- Implementar integração com outra plataforma interna sem definição específica.
- Refazer a interface completa ou substituir funcionalidades posteriores por limitações da versão demonstrada em 14/10.

## 5. Critérios de aceite e teste real

Validar com uma gravação autorizada que contenha compartilhamento de tela e várias etapas de um processo. Usar também um trecho em que algo seja explicado sem aparecer visualmente, para conferir o tratamento de lacunas.

- [ ] O app gera um procedimento numerado com ações e telas correspondentes, além do resumo geral.
- [ ] As evidências são imagens reais da gravação e correspondem às etapas descritas.
- [ ] O texto usa o contexto falado sem inventar campos, regras ou resultados.
- [ ] Etapas sem evidência visual são sinalizadas claramente.
- [ ] O PDF baixado contém os prints, as legendas e as descrições, inclusive aberto offline.
- [ ] Não há imagens quebradas, deformadas ou cortadas pela paginação de modo que comprometa a compreensão.
- [ ] Se DOCX já estiver disponível, ele também mantém texto e imagens correspondentes.
- [ ] A documentação continua compreensível sem reproduzir o vídeo.
- [ ] O checklist escolhido influencia a entrega gerada e os perfis gerais continuam disponíveis.
- [ ] A API, o banco, a autenticação e as permissões existentes foram preservados.

Ao terminar, informar quais arquivos/componentes foram alterados, quais testes foram executados e disponibilizar um documento de exemplo gerado com material autorizado. Diferenciar **implementado**, **validado com geração real** e **pendente de validação**. Mockups e dados simulados não comprovam o resultado da análise nem a qualidade do arquivo exportado.

## 6. Referência disponível e estado conhecido

Repositório de referência: https://github.com/henriquecunha-byte/rpadiscovery

- O checkout de referência já contém implementação de PDF/Word com imagens, posterior à reunião. Isso não comprova que a mesma implementação esteja presente ou funcionando neste projeto Lovable.
- Os ajustes de contexto, checklists e revisão estão no commit **1c86ded47c368673815dc805c668f4d852988368**, com referência reutilizável em **integrations/context-ui**.
- Os testes locais realizados nessa rodada cobriram o formulário e suas regras. Não validaram a geração documental no app publicado do Lovable.
- Inspecionar primeiro o projeto Lovable atual. Reaproveitar apenas a lógica necessária, adaptada aos serviços que já estão configurados nele.

**Resultado esperado:** enviar uma gravação de discovery e receber um documento que permita acompanhar o processo tela a tela, com imagens e descrições suficientes para revisão com o cliente.
