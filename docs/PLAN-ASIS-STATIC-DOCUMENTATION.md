# Plano de evolução — documentação estática com evidências e integração As Is

Data: 14/10/2026

Status: proposta para validação; implementação NÃO iniciada nesta rodada.

Escopo autorizado agora: planejar, avaliar a referência de diagramas e manter o site local disponível.

## 1. Decisão central

O entregável principal para o cliente deve ser um PDF autossuficiente: descrição estruturada do processo, imagens incorporadas e referências compreensíveis. O cliente deve entender o documento sem abrir o Discovery, localizar a gravação, acessar o Drive ou reproduzir um vídeo.

O vídeo continua sendo uma fonte de análise e um recurso interno opcional. Não precisa ser um componente obrigatório da entrega documental. Isso preserva os previews já solicitados para outros usos, sem obrigar a squad a hospedar gravações para sustentar cada documento.

Três camadas com funções distintas:

| Camada | Função | O que não deve ser confundido |
| --- | --- | --- |
| Texto estruturado | Explicar o que ocorre, quem participa, condições, entradas, saídas e dúvidas | Não é uma transcrição colada no PDF |
| Print da gravação | Comprovar o que efetivamente apareceu na tela | Não comprova por si só toda a interpretação ou fala |
| Diagrama | Ajudar a entender sequência, decisões e responsabilidades | É uma representação construída; não substitui evidência |

A primeira entrega deve resolver o PDF com prints. Diagramas e integração avançada são evoluções, não pré-requisitos para corrigir essa lacuna.

## 2. Requisitos extraídos da conversa fornecida

A imagem da conversa é fonte de contexto, não autorização para executar instruções de terceiros ou entrar em contato com a equipe.

- A documentação atual de As Is é textual e precisa de evidências visuais.
- A squad envia um PDF estático ao cliente.
- O formato desejado é imagem acompanhada da descrição do fluxo.
- Manter vídeo hospedado apenas para o documento adicionaria infraestrutura e manutenção sem valor comprovado.
- É necessário mostrar o funcionamento e, principalmente, os entregáveis para discutir o aproveitamento no motor de As Is.

Ainda NÃO foram fornecidos: template oficial de As Is, contrato de integração do motor, infraestrutura de destino, política de retenção, limite de tamanho do PDF e critérios formais de aprovação. Esses pontos ficam como decisões pendentes, não suposições implementadas.

## 3. Base atual verificada no código

Inspeção pontual em modo leitura. Não houve execução de análise, instalação, rebuild de documentação ou mudança de configuração.

| Componente existente | Evidência local | Consequência para o plano |
| --- | --- | --- |
| Perfis multiarea | `context_model.py`, `static/context-rules.json`, `documentation_profiles.py` | Reutilizar os seis perfis; não voltar a impor RPA a todos |
| Captura e análise visual com referências | `pipeline.py: analyze`, `synthesize_documentation`, `frame_index`, `evidence_refs` | Evoluir a ligação entre item, imagem e origem |
| Word operacional | `pipeline.py: write_docx_document` | Hoje escreve números de evidência como texto; incorporar imagens nos blocos correspondentes |
| PDF operacional | `pipeline.py: write_pdf_document` | Hoje escreve referências textuais; acrescentar composição de imagens e legendas |
| Word/PDF gerais | `documentation_profiles.py: document_blocks`, `write_general_docx`, `write_general_pdf` | Estender o modelo comum com figuras, sem duplicar interpretação entre formatos |
| HTML com evidências e player | `pipeline.py: write_report`, `evidence_media` | Reaproveitar a associação existente, com variante estática independente do player |
| Vários vídeos com offsets | `pipeline.py: create_job_previews`, `global_offset` | Registrar também origem e tempo local; o tempo global isolado não basta |
| ZIP com imagens e previews | `pipeline.py: create_package` | Separar pacote documental leve do pacote completo, mantendo compatibilidade |
| Reconstrução com área temporária | `orchestrator.py: rebuild` | Reutilizar a proteção por staging e testar falhas durante a publicação |

A lacuna atual é concreta: já há imagens capturadas e associações às falas, mas os exportadores estáticos não compõem essas imagens dentro do documento. Um player no HTML não resolve o PDF enviado ao cliente.

O site local respondeu HTTP 200 em `http://127.0.0.1:8770/`. Foi mantido no processo existente, sem reinício. A disponibilidade foi conferida pontualmente; não foi criado monitor contínuo.

## 4. Produto proposto: perfil e tipo de entrega independentes

Manter separados dois conceitos:

1. **Perfil do conteúdo:** Personalizado, Reunião, Treinamento, Entrevista, Pesquisa ou Processo / RPA.
2. **Tipo de entrega:** Documentação estática, ou Documentação + previews.

Para o uso de As Is, propor Documentação estática como configuração preferencial, sujeita à validação da equipe. Pedidos antigos preservam o comportamento anterior. Nenhum preview ou arquivo existente deve ser removido automaticamente.

| Saída | Documentação estática | Documentação + previews |
| --- | --- | --- |
| PDF com imagens incorporadas | Sim | Sim |
| Word editável com imagens | Sim | Sim |
| HTML estático para consulta | Sim, sem dependência de player | Sim; consulta em vídeo pode ser adicional |
| Dados estruturados + evidências aprovadas | Sim, no pacote interno/importável | Sim |
| MP4 cortado por gravação | Não gerar nesse modo | Preservar geração individual |
| Roteiro de cortes | Não obrigatório | Preservar |
| Gravação original no pacote do cliente | Não, por padrão | Também não incluir automaticamente |

A UI deve dizer claramente quando previews não foram solicitados; não apresentar isso como falha de processamento. O usuário deve saber o que será gerado antes de iniciar.

Separar também **pacote interno** de **documento para cliente**: transcrição bruta, guia interno, nomes de arquivo, notas de revisão e dados de integração não devem entrar automaticamente na entrega externa. Hoje o guia aparece nas exportações; a nova regra precisa ser deliberada e configurável.

## 5. Estrutura do PDF de As Is

Proposta inicial a ajustar ao template oficial:

1. Identificação: título, área/processo, versão, data e status de revisão.
2. Objetivo e limites do levantamento.
3. Visão geral do fluxo; diagrama somente quando sustentado pelos dados.
4. Papéis e sistemas confirmados.
5. Descrição das etapas com imagens e legendas.
6. Regras, decisões e exceções observadas ou relatadas.
7. Dúvidas, divergências e informações não demonstradas.
8. Índice de evidências, quando o volume justificar.

Recomendações e oportunidades de automação ficam em seção explicitamente separada do estado atual. Não transformar uma sugestão de To Be em uma etapa de As Is.

### Bloco de etapa

- Identificador estável e título específico.
- Explicação da ação e do resultado esperado, na linguagem do público.
- Responsável/papel e sistema, quando identificados.
- Entrada, saída e condição de execução, quando confirmadas.
- Print contextualizado e legenda sobre o que ele mostra.
- Origem: gravação identificável e tempo local.
- Natureza do suporte: demonstrado em tela, relatado na fala ou ponto a validar.
- Regra ou exceção associada, se houver.

Uma etapa pode ter mais de uma evidência. Uma evidência pode sustentar vários itens. Evitar repetir a mesma imagem em páginas sucessivas: usar referência interna à figura quando a leitura continuar clara.

Se só houve relato verbal, registrar essa condição. Não inventar screenshot, interface, botão, nome de participante ou campo para preencher a página.

### Adaptação aos demais perfis

A composição de figuras deve ser comum; a narrativa permanece específica:

- Reunião: decisões, justificativas e encaminhamentos, com prints apenas quando relevantes.
- Treinamento: conceitos e demonstrações em sequência didática.
- Entrevista: perguntas, respostas e achados, sem tratar opinião como fato.
- Pesquisa: observações, hipóteses, evidências e limitações.
- Personalizado: organização orientada ao pedido, sem campos operacionais obrigatórios.

Não incluir fotos de participantes como decoração para cumprir uma cota de imagens.

## 6. Seleção de evidências e rastreabilidade

### 6.1 Fluxo de preparação

1. Identificar itens e afirmações relevantes a partir da fala e do objetivo.
2. Localizar janelas de tempo relacionadas a esses itens.
3. Reaproveitar as imagens disponíveis; capturar novos frames apenas quando necessário.
4. Escolher frames legíveis que mostrem a informação citada, e não apenas coincidam com o minuto.
5. Associar cada imagem ao item e ao trecho de fala que a contextualiza.
6. Identificar repetições e telas sem conteúdo útil.
7. Gerar cópias apropriadas à exportação, preservando originais.
8. Revisar o conjunto antes de distribuir como documento aprovado.

A ordem narrada na reunião nem sempre é a ordem real do processo. Ordenar etapas exige evidência de sequência, não apenas ordenar screenshots por tempo.

### 6.2 Contrato interno proposto

Evolução versionada do esquema atual, com adaptadores para arquivos antigos. Os nomes abaixo são proposta, não uma API já existente.

| Entidade | Campos essenciais |
| --- | --- |
| Documento | `schema_version`, `document_id`, `revision`, `profile`, `delivery_mode`, `review_status` |
| Fonte | `source_id`, nome de exibição, duração, identificador/hash, referência interna protegida |
| Item/etapa | `item_id`, descrição, `evidence_refs`, referências de transcrição, situação de validação |
| Evidência | `evidence_id`, `source_id`, tempo local/global, caminho relativo, dimensões, legenda, hash do asset |
| Relação | item, evidência, trecho da fala e o que essa combinação sustenta |
| Diagrama | `diagram_id`, tipo, nós/arestas com `item_refs`, versão do modelo visual e estado de revisão |
| Exportação | arquivo, revisão, formato, checksum e avisos de completude |

Não persistir URLs públicas ou temporárias como única origem de uma evidência. Não expor caminho absoluto do computador, segredo, token ou credencial no documento/manifesto.

IDs e hashes ajudam a rastrear versões; não comprovam, por si só, que a interpretação está correta ou que a imagem é suficiente. Decisões sem imagem continuam vinculadas à fala, com status explícito.

### 6.3 Revisão humana

Estados propostos: rascunho, em revisão e aprovado. Aprovação deve registrar a pessoa que validou e a revisão exata; não confundir “arquivo gerado” com “conteúdo aprovado”.

No MVP, permitir revisão humana dos arquivos sem depender de um editor completo. Na evolução da UI, incluir:

- trocar/remover imagem e selecionar outro instante da mesma fonte;
- editar legenda e texto sem refazer transcrição;
- marcar “somente relato verbal”;
- revisar dados sensíveis;
- regenerar documentos sem gerar novamente os previews;
- invalidar a aprovação quando o conteúdo aprovado mudar.

Não liberar publicação externa automática como parte desta iniciativa.

## 7. Qualidade visual, privacidade e portabilidade

### PDF e Word

- Imagens realmente incorporadas, nunca apenas um link ou endereço externo.
- Texto selecionável, títulos hierárquicos, numeração e legendas consistentes.
- Tamanho de imagem calculado pela área útil da página; dividir detalhes em figuras legíveis em vez de reduzir tudo a uma miniatura.
- Preservar proporção. Recortes devem manter contexto suficiente e indicar que são recortes.
- Evitar print separado de sua legenda e páginas com texto cortado, tabelas transbordando ou blocos maiores que uma página.
- Padronizar tamanho de página após validar o template; hoje o legado operacional usa Letter e os perfis gerais usam A4.
- Usar a identidade Btime já fornecida. Conferir licença de incorporação de fontes; manter fallback explícito quando necessário.
- Orçamento de tamanho do arquivo definido com a squad; comprimir após medir legibilidade, sem prometer um limite antes da amostra.
- Não afirmar conformidade PDF/UA sem validação específica. Manter alternativa acessível em HTML/Word.

### Dados sensíveis

O controle atual é uma orientação ao processamento, não uma garantia de anonimização automática de mídia. A versão estática deve tratar isso explicitamente:

- revisar imagens, texto, legendas, metadados e nomes de arquivo;
- não considerar uma tarja visual sobreposta como remoção segura de dados;
- quando houver ocultação, exportar uma cópia efetivamente sanitizada, sem camada recuperável do conteúdo oculto;
- impedir que o ZIP do cliente inclua o original não sanitizado por engano;
- conservar original apenas conforme política aprovada e com acesso apropriado.

Essas regras são critérios de produto; não substituem a definição corporativa de privacidade e retenção.

### Armazenamento e custo

PDF offline elimina a necessidade de hospedar vídeo para o leitor. Não elimina o armazenamento temporário de ingestão nem o custo de transcrição/análise.

Propor captura seletiva, reaproveitamento de transcrição/análise e regeneração por etapa. Desativar previews deve evitar a renderização dos MP4, não apenas esconder o botão de download.

Medir tempo e uso de recursos por fase em uma amostra real autorizada. Não prometer redução percentual ou prazo sem medição.

Retenção e exclusão de fontes precisam de decisão explícita. Não implementar limpeza automática agora; considerar o impacto sobre “retomar”, trocar screenshots e auditar evidências antes de definir qualquer prazo.

## 8. Avaliação do repositório diagram-design

Referência fornecida: [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design).

Commit de main consultado pela API em 14/10/2026: `11b08eade8049c441ed3df1895e3b527c26c0fbe` (13/10/2026). Fixar e rever a versão na futura prova de conceito.

### O que foi verificado

- O projeto é uma skill com referências, templates e scripts locais; gera HTML/SVG e documenta exportação PNG. Não é uma API SaaS pronta de processamento de documentos. [README](https://github.com/cathrynlavery/diagram-design)
- Há padrões para fluxogramas e raias por responsável, pertinentes à descrição de processos. [Flowchart](https://github.com/cathrynlavery/diagram-design/blob/main/skills/diagram-design/references/type-flowchart.md), [Swimlane](https://github.com/cathrynlavery/diagram-design/blob/main/skills/diagram-design/references/type-swimlane.md).
- A exportação SVG tem um helper próprio; o procedimento de PNG usa renderização em navegador. Essa separação é compatível, em princípio, com gerar uma imagem para o documento. Não foi executada nesta avaliação. [Exportação](https://github.com/cathrynlavery/diagram-design/blob/main/skills/diagram-design/references/export.md), [helper SVG](https://github.com/cathrynlavery/diagram-design/blob/main/skills/diagram-design/scripts/export_svg.py).
- A licença principal é MIT, com preservação dos avisos aplicáveis em cópias/partes substanciais. Dependências e assets têm avisos próprios a conferir na adoção. [Licença](https://github.com/cathrynlavery/diagram-design/blob/main/LICENSE), [terceiros](https://github.com/cathrynlavery/diagram-design/blob/main/THIRD_PARTY_LICENSES.md).
- A política informa que o plugin não mantém um servidor próprio, mas o provedor de IA processa os insumos e fontes podem ser carregadas do Google Fonts. Portanto, “arquivo autocontido” não deve ser interpretado como “zero rede” sem adaptação e teste. [Privacidade](https://github.com/cathrynlavery/diagram-design/blob/main/PRIVACY.md).

### Parecer para este projeto

**Adequado como referência visual e candidato a componente de exportação. Adoção em produção ainda não aprovada.**

O caminho recomendado é usar templates e regras visuais revisados para transformar um modelo estruturado do processo em um diagrama. Não adicionar uma chamada livre de agente a cada documento apenas para redesenhar caixas.

O documento estruturado continua sendo a fonte de verdade. O diagrama é uma projeção; editar o gráfico não deve silenciosamente alterar regras ou evidências.

Manter JSON de nós/arestas e os fontes HTML/SVG no pacote interno. Isso permite reconstrução técnica, mas não equivale a um editor visual amigável para a squad. Se edição por arrastar e soltar for requisito, avaliar um formato próprio de edição como decisão separada.

### Prova de conceito futura

1. Selecionar um fluxograma curto com decisão e um fluxo com duas ou três áreas.
2. Usar dados sintéticos ou anonimizados autorizados.
3. Preservar os mesmos IDs de etapas e referências dos documentos.
4. Aplicar cores, tipografia e espaçamento Btime com recursos locais autorizados.
5. Gerar HTML/SVG estáticos; exportar uma imagem para Word/PDF.
6. Abrir o PDF offline e inspecionar leitura em página real.
7. Registrar qualquer agrupamento ou simplificação; não omitir decisões importantes para “caber”.
8. Testar um processo maior: dividir visão geral e subfluxos, sem reduzir texto até ficar ilegível.
9. Aprovar a ferramenta somente se passar em fidelidade, legibilidade, manutenção e execução local.

No primeiro ciclo, adotar apenas dois tipos de diagrama. Gráficos sem necessidade informativa, animações e galeria de dezenas de estilos ficam fora do escopo.

### Cuidados de integração

- Diagramas são síntese visual, nunca prints “gerados” para representar uma tela real.
- Mostrar somente atores, sistemas, conexões e condições sustentados pelas fontes. Relação inferida fica indicada ou aguarda validação.
- Renderizar a partir de templates confiáveis. Não executar HTML, JavaScript ou SVG arbitrário vindo da transcrição/modelo.
- Restringir tags, atributos, links, referências de arquivo e rede; executar o render isolado com limites de tempo e tamanho.
- Usar fontes locais ou fallback; testar com rede bloqueada.
- Tratar indisponibilidade do renderer como falha do diagrama, não como perda de toda a documentação.
- Não instalar a skill na apresentação nem alterar configurações globais para esta avaliação.

## 9. Integração futura com o motor de As Is

O motor não foi inspecionado. Não presumir stack, endpoints, autenticação, formatos, editor ou armazenamento. Esta etapa depende de alinhamento com seus responsáveis.

### Caminho recomendado

Começar por um pacote de intercâmbio versionado contendo JSON estruturado, imagens revisadas e manifesto, sem exigir upload permanente de vídeo. O motor pode consumir esse pacote e encaixar os blocos no template existente.

Só depois de validar o contrato de dados decidir entre importação de arquivo e integração por API. Isso permite validar a utilidade do output antes de acoplar dois sistemas.

### Informações a confirmar

- O motor já recebe JSON, HTML, Markdown ou outro formato?
- Quem é responsável pelo documento final: Discovery ou motor?
- Há IDs de processo, etapa, cliente/organização e revisão que devemos preservar?
- Como imagens são recebidas: pacote, anexo ou armazenamento autorizado?
- Há revisão humana e versionamento no destino?
- Como tratar atualizações, conflitos e reimportações?
- Quais limites de arquivo, privacidade e retenção são exigidos?
- O cliente recebe apenas PDF ou também Word/arquivos de suporte?

### Critérios do contrato

- Versionamento explícito e validação antes de importar.
- Chave de idempotência vinculada a documento/revisão para não duplicar etapas.
- Preservação de IDs e proveniência, sem caminhos locais ou tokens no payload.
- Isolamento por organização/usuário; identidade confirmada no servidor, nunca confiada a um campo enviado pelo navegador.
- Imagens sanitizadas no canal de cliente e originais restritos quando autorizados.
- Falha recuperável, mensagens seguras e logs sem conteúdo sensível.
- Documentação estática continua utilizável mesmo que a integração esteja indisponível.

Não conectar Supabase, OAuth ou conta corporativa nesta rodada.

## 10. Plano de execução por etapas e critérios de saída

Toda execução abaixo depende de nova autorização. P0/P1/P2 são prioridades, não prazos assumidos.

| Etapa | Prioridade | Entrega | Dependência | Critério para avançar |
| --- | --- | --- | --- | --- |
| 0. Alinhamento | P0 | Template, amostra sanitizada, formato de entrega e responsáveis de revisão | Squad | Estrutura e critérios de aceite acordados |
| 1. Catálogo de evidências | P0 | IDs, origem/tempo local, associação com itens e cópias de exportação | Amostra e esquema versionado | Nenhuma referência inválida; provas distinguem tela, fala e dúvida |
| 2. Exportação estática | P0 | PDF/Word com figuras, legendas e pacote sem vídeo | Catálogo | Arquivos legíveis e completos offline; imagens corretas ao lado do conteúdo |
| 3. Revisão e modos de entrega | P1 | Seleção documental/com previews, revisão e regeneração independente | Exportadores | Guia/revisão preservados; documento gerado não é rotulado aprovado sozinho |
| 4. Prova de diagramas | P1 | Dois padrões visuais Btime e decisão de adoção do repositório | Conteúdo estruturado confiável | Fluxo fiel, legível e exportável sem rede |
| 5. Adaptador As Is | P1 | Pacote importável; API somente se acordada | Contrato do motor | Importação/reimportação sem perda de imagens, significado ou IDs |
| 6. Piloto e liberação | P0 para liberar | Amostra real autorizada, revisão da squad e comparação com documento atual | MVP pronto | Todos os critérios críticos aprovados e limitações registradas |
| 7. Otimização | P2 | Medições e ajustes de tempo, peso e reaproveitamento | Dados do piloto | Ganho medido sem perda de fidelidade ou rastreabilidade |

**MVP mínimo:** etapas 0, 1, 2 e 6, com revisão humana explícita. Diagrama e API não bloqueiam a primeira entrega de PDF com evidências. A UI completa de revisão pode vir depois; não adiar a validação humana até lá.

### Mapa de implementação futura

- `context_model.py`, `schemas.py` e frontend de contexto: tipo de entrega independente do perfil, mantendo contratos antigos.
- Novo módulo de catálogo de evidências: resolução segura de IDs, imagem, origem e legenda compartilhada entre exportadores.
- `pipeline.py` e `documentation_profiles.py`: incorporar figuras aos blocos; preservar campos e guias dos perfis existentes.
- `orchestrator.py`: revisão documental sem recodificar vídeo; tratar modo sem preview como resultado esperado.
- `api.py` e autorização: servir imagens/artefatos somente ao proprietário; publicar novas revisões sem perder a anterior em caso de falha.
- Novo adaptador de diagramas, se aprovado: receber dados estruturados, não arquivos executáveis livres.
- Empacotamento: manifesto explícito de arquivos por destino, evitando incluir sobras de outros modos.
- Testes: expandir fixtures atuais; nunca usar o banco de apresentação para testar novas migrações.

Esses módulos são pontos de intervenção propostos. Nenhum foi alterado por este planejamento.

## 11. Matriz de aceite a executar na implementação

| Cenário | Prova necessária | Impede liberação? |
| --- | --- | --- |
| PDF sem rede e sem pasta do job | Copiar só o PDF para local isolado: figuras e texto completos | Sim |
| Word em leitor real | Abrir/renderizar, revisar páginas, legendas e imagens; XML sozinho não basta | Sim para prometer Word final |
| Correspondência item ↔ imagem | Revisão da squad com fontes; nenhuma imagem de outra etapa/arquivo | Sim |
| Múltiplas gravações | Fonte e tempo local corretos inclusive em itens que cruzam arquivos | Sim |
| Relato sem tela | Identificado como relato; sem print inventado nem ator presumido | Sim |
| Prints repetidos/ilegíveis | Seleção alternativa ou aviso; sem perda de mudanças relevantes | Sim |
| Dados sensíveis | Cópia externa sem conteúdo oculto recuperável, metadados ou originais vazados | Sim |
| PDF longo e tabela extensa | Todas as páginas renderizadas e conferidas; nenhuma colisão/corte | Sim |
| Modo documental | Sem renderização MP4 desnecessária; estado “não solicitado” correto | Sim para esse modo |
| Compatibilidade | Pedidos/rascunhos antigos, previews individuais e ZIP completo preservados | Sim |
| Falha/cancelamento | Entrega anterior íntegra; nenhuma promoção parcial silenciosa | Sim |
| Autorização | Imagem, documento e pacote de outra conta/organização inacessíveis | Sim para uso com contas |
| Diagrama | Nós/arestas fiéis, sem conexão inventada ou rótulo ilegível; offline | Sim para liberar diagramas |
| Integração | Reimportar mesma revisão sem duplicar; versões incompatíveis rejeitadas claramente | Sim para liberar integração |
| Desempenho | Tempos por fase e tamanho por perfil registrados em amostras comparáveis | Não fixar meta antes da linha de base |

Aplicar Product QA Guardrails quando houver implementação de UI: clareza dos campos/estados, uma decisão distinta por etapa, vazios com próximo passo e confirmação específica para descarte/substituição. **Ainda não há PASS/FAIL da interface futura: estes são critérios planejados.**

Piloto proposto: um processo simples com tela compartilhada, um caso com decisão/exceção, um conjunto de várias gravações e um material sem evidência visual. Revisar com pessoas responsáveis pelo conteúdo. Amostras pequenas aprovadas não justificam prometer acerto em qualquer reunião.

## 12. Decisões a levar à equipe

| Decisão | Proposta inicial | Quem deve validar |
| --- | --- | --- |
| Entrega ao cliente | PDF estático com imagens e texto | Responsável pela documentação/squad |
| Template | Reutilizar a estrutura corporativa de As Is | Squad e responsável pelo motor |
| Vídeo | Apoio interno opcional, não dependência do PDF | Produto e operação |
| Aprovação | Revisão humana identificada por versão | Dono do processo e squad |
| Diagramas | Começar com fluxograma e raias | Produto/design e squad |
| Integração | Pacote versionado antes de API acoplada | Responsável técnico pelo motor |
| Retenção e sanitização | Política explícita antes de apagar/distribuir | Responsáveis corporativos apropriados |
| Limite do arquivo | Definir após primeira amostra legível | Squad e canal de entrega |

A falta dessas respostas não impede este planejamento. Impede assumir como definitivas a estrutura corporativa, retenção e arquitetura de integração.

## 13. Como posicionar na apresentação de hoje

**Demonstrável na versão atual:** envio de gravações, contexto personalizado, perfis, documentos estruturados, evidências no HTML e previews individuais.

**Próxima evolução planejada:** incorporar prints à descrição de cada etapa no PDF/Word, permitir entrega documental sem vídeo e avaliar diagramas/integrador As Is.

Mensagem sugerida, sem apresentar futuro como funcionalidade pronta:

> “Hoje o Discovery organiza o conteúdo das gravações e conecta a documentação às evidências. O próximo passo, alinhado à squad, é entregar essas imagens dentro do próprio PDF, junto da descrição do fluxo, sem depender de hospedagem de vídeo para o cliente.”

Mostrar somente material autorizado ou sintético. Não prometer integração já conectada, anonimização automática ou redução de tempo ainda não medida.

## 14. Registro desta rodada

- Aplicação, arquivos de trabalho e banco: nenhuma alteração executada.
- Servidor local: conferência por leitura, sem reinício ou encerramento.
- Repositório de diagramas: documentação/código consultados, sem clone, instalação ou execução.
- Entregável desta rodada: este plano.
- Não houve chamadas de inferência da aplicação, geração de mídia, commit, push, deploy ou contato com terceiros.
- O custo e a ordem da implementação deverão ser estimados por etapa após validar template, amostra e contrato do motor.
