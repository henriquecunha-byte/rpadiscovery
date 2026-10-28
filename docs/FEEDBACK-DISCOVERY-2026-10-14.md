# Feedbacks da reunião de Discovery — 14/10/2026

Revisão em 19/10/2026. Resultado: os ajustes centrais pedidos na reunião continuam pendentes; há componentes existentes que podem ser reaproveitados.

Registro histórico da análise anterior à implementação. Após autorização de Henrique, a rodada de correções foi executada e está descrita em [Implementação e QA de 19/10](QA-STATIC-EVIDENCE-2026-10-19.md), incluindo as pendências de integração e aceite visual.

## 1. Fonte, recorte e método

Fonte: `Ferramenta de Discovery - 2026_10_14 15_31 GMT-03_00 - Recording.mp4`, fornecida pelo Henrique.

- Duração: 28min29,75s.
- Tamanho: 321.738.349 bytes.
- SHA-256 do original: `ADEDA993E6AB407E48E1A2DF3A366288F6CD78EAB51FC9E02A869AE88FF2E409`.
- Limite informado pelo Henrique para o bloco do Hiago: 18:30.
- A conversa começa efetivamente por volta de 05:24, após espera inicial.
- A opinião técnica solicitada ao Lucas começa por volta de 17:34, dentro desse mesmo bloco. O limite de 18:30 separa os assuntos; não significa que só o Hiago fala antes dele.
- Em 18:27–18:37 surge a proposta de outra chamada e o tema muda para motion. A gravação continua na mesma chamada, conforme o contexto informado pelo Henrique.

Foi gerada transcrição local com Faster-Whisper small, marcações de tempo e inspeção de frames da demonstração. Os tempos abaixo são da gravação original, incluindo a espera inicial.

Não há diarização automática confiável. A atribuição dos pedidos usa o recorte indicado pelo Henrique e o contexto explícito da conversa — inclusive o chamado nominal ao Lucas antes da opinião técnica. Grafias de nomes de sistemas na transcrição automática podem variar; não foram usadas para presumir um contrato técnico.

Comparação com o checkout atual de `G:\Repositorios\btime-rpa-docs`, por leitura de código. Esta rodada não executa QA funcional da aplicação ou uma integração real com Drive. “Existente no código” não significa que foi implementado em resposta a esta reunião.

## 2. Conclusão

A generalização para diferentes áreas, os downloads e os previews já estavam na demonstração. Portanto, não comprovam uma rodada posterior de atendimento aos feedbacks.

O pedido de documentação ficou mais específico do que “gerar um fluxo operacional”: o Hiago espera um **passo a passo tela a tela, com prints**, utilizável para documentar o processo com o cliente. Hoje o Word/PDF trazem referências textuais às evidências; as imagens e os players ficam no HTML.

A sugestão nova de arquitetura é do Lucas: usar a estrutura corporativa do Drive para guardar os arquivos do projeto e acessá-los pela API. O app já tem um conector de importação e envio de ZIP, mas isso ainda não constitui o armazenamento remoto de todos os arquivos da aplicação.

## 3. Matriz dos pedidos e cobertura atual

| ID | Momento | Origem | Pedido observado | Estado atual | Evidência no projeto |
| --- | --- | --- | --- | --- | --- |
| H1 | 12:47–13:39 | Hiago | Mostrar o documento gerado com prints; os prints são o principal valor documental | **Pendente no documento estático** | `pipeline.py:write_docx_document` e `write_pdf_document` escrevem “Evidências: …” como texto. Os exportadores gerais em `documentation_profiles.py` também não incorporam imagens |
| H2 | 13:39–14:00 | Hiago | Usar imagens como evidência complementar à gravação na documentação do cliente | **Parcial** | Há captura em `extract_evidence`, arquivos em `evidence/`, referências `evidence_refs` e matriz CSV. A composição do PDF com essas imagens permanece ausente |
| H3 | 15:10–15:58 | Hiago | Priorizar um gerador de passo a passo **tela a tela**; fluxo operacional textual, isoladamente, não equivale a isso | **Parcial** | Existem etapas com descrição, responsável, sistema, entradas/saídas e referências. Falta materializar a sequência visual em blocos com imagem, legenda e ação correspondente |
| H4 | 15:10–15:26 | Hiago | Conversar com o responsável pela ferramenta interna para incorporar a solução | **Pendente; planejado** | O plano de 14/10 descreve uma futura integração As Is. Não há adaptador para esse motor identificado nesta revisão |
| L1 | 17:34–17:55 | Lucas, após ser chamado em 15:58–16:23 | Reaproveitar a experiência do Argus e organizar uma pasta do projeto dentro da estrutura Btime no Drive | **Parcial — conector já existe** | `drive.py` aceita pasta de destino, lista arquivos e faz OAuth. Não há fluxo de provisionamento e administração de uma pasta remota por projeto como armazenamento principal |
| L2 | 17:55–18:13 | Lucas | A aplicação administrar os arquivos no Drive e buscá-los pela API | **Pendente como arquitetura de armazenamento** | Importação em `api.py:import_from_drive` baixa fontes para `jobs/<id>/input`. `send_to_drive` envia apenas `entrega-completa.zip`. O pipeline continua operando sobre arquivos locais |
| C1 | 12:03–12:46 | Esclarecimento durante a demonstração | Recortar vídeo, capturar prints e transcrever | **Existente no código e demonstrado** | `extract_evidence`, `transcribe` e `create_job_previews`. É cobertura de base, não um novo ajuste posterior |
| C2 | 08:08–09:23 e 09:42–10:21 | Apresentação do Henrique | Diferentes contextos/perfis e formatos de download | **Existente na demonstração** | Perfis em `context-rules.json` e contratos/exportadores por perfil. Também não deve ser contado como atendimento posterior a esta reunião |

### H1/H2 — O que precisa mudar no documento

Em 12:47 o pedido é ver o documento com prints. Em aproximadamente 13:31–13:58, o Hiago reforça que as imagens são o principal valor para documentação de RPA e para comprovar o processo ao cliente. Em 14:14–14:29, a demonstração reconhece que o PDF não contém esses prints.

Para atender:

- Cada etapa relevante deve mostrar o print real incorporado ao PDF.
- A imagem deve acompanhar a ação, a descrição e uma legenda útil.
- Fonte e tempo da gravação servem para rastreabilidade, sem exigir vídeo hospedado para compreender a etapa.
- Replicar o bloco no Word é a recomendação de consistência com os formatos já oferecidos; o pedido visual explícito na chamada se concentra no documento mostrado, o PDF.
- Capturar o arquivo JPG ou listar um número de evidência não basta para considerar o pedido entregue.

### H3 — A correção que não pode se perder

Por volta de 15:32, o Henrique aponta o fluxo operacional como um possível passo a passo. Em 15:42–15:58, o Hiago esclarece que o gerador esperado é **tela a tela**, com as ações organizadas em passos.

O critério de aceite deve avaliar:

1. A pessoa consegue seguir a sequência de telas com base no documento.
2. Cada print mostra a tela/estado relativo à ação descrita.
3. Mudanças de tela importantes não desaparecem em um resumo genérico.
4. A ausência de demonstração é indicada, sem inventar telas ou cliques.
5. O print fica no corpo da etapa; um anexo descontextualizado não substitui a sequência.

Isso não exige inserir todos os frames da gravação. Exige selecionar as imagens que explicam os passos, preservar a relação com a fala e manter a sequência do processo demonstrado.

### H4 — Integração interna

O Hiago propõe conversar com o responsável pela ferramenta interna e incorporar a solução. O nome do destino na transcrição automática não é suficientemente seguro para fixar uma API ou produto apenas com base nele; a conversa fornecida anteriormente pela Mari identifica o contexto como motor de As Is.

O próximo alinhamento deve confirmar o nome/escopo do destino, o modelo de documento e como o gerador deve entregar texto, imagens e referências. Nesta rodada não houve contato com essa pessoa, inspeção do motor ou integração.

### L1/L2 — O que o Lucas propôs e o que já existe

O Lucas é chamado nominalmente para dar a opinião técnica. Após um problema de áudio, a orientação sobre Drive aparece em 17:34–18:13:

- usar a experiência de integração já existente no Argus;
- reservar uma pasta para este projeto na estrutura corporativa;
- a aplicação salvar e administrar os arquivos no Drive;
- consultar os arquivos por API.

A fala menciona processamento em Supabase como referência à solução descrita pelo Lucas. Isso não define, sozinho, onde FFmpeg, transcrição ou workers deste projeto devem executar.

Também aparece a expressão “armazenamento infinito”. Ela não deve virar premissa de capacidade: limites, permissões, retenção e acesso precisam ser confirmados no ambiente corporativo efetivamente utilizado.

A implementação atual cobre funções úteis, mas de alcance menor:

| Capacidade | Situação encontrada |
| --- | --- |
| Listar vídeos/ZIPs e pastas do Drive | Código existente |
| Selecionar arquivos e importá-los | Código existente; faz download para processamento local |
| Escolher uma pasta e enviar o ZIP final | Código existente, por `upload_package` |
| Criar/administrar a estrutura remota por projeto/job | Não identificado |
| Persistir cada fonte, print, documento e vídeo com IDs remotos | Não identificado |
| Reabrir/servir os assets a partir do Drive, sem depender do job local | Não identificado |
| Vincular a integração corporativa do Argus a este app | Não realizado por esta revisão |

Essas funções de Drive estão atualmente restritas ao ambiente local. A guarda `access.py:require_local_drive` bloqueia a conexão por usuário autenticado, indicando que ela ainda não está configurada. Isso reforça que o conector disponível não representa uma integração corporativa por integrante pronta para produção.

A validação das credenciais corporativas, pasta e permissões deve ocorrer com o responsável pela integração. Nenhum token foi lido, copiado ou alterado nesta análise.

## 4. O que já foi coberto pelo planejamento de 14/10

Referência: [Plano de documentação estática e As Is](PLAN-ASIS-STATIC-DOCUMENTATION.md).

| Tema da reunião | Cobertura do plano anterior | Ajuste de entendimento |
| --- | --- | --- |
| PDF autossuficiente com imagens | Já previsto como prioridade | O vídeo confirma a prioridade com a necessidade da squad |
| Passo a passo visual | Etapas com imagens já propostas | Tornar “tela a tela” um critério obrigatório, não apenas um enriquecimento do fluxo textual |
| Vídeos como apoio | Modos documental e com previews já propostos | Preservar a utilidade interna do vídeo sem condicionar a leitura do PDF a ele |
| Integração As Is | Já prevista, com contrato pendente | Confirmar o destino e alinhar o gerador de passos com seu responsável |
| Drive como armazenamento dos arquivos | O plano discutia retenção/infra e pacote de intercâmbio | **Detalhe novo da reunião:** proposta concreta baseada no Argus, com pasta corporativa e API de Drive |
| Diagramas via diagram-design | Referência adicional fornecida pelo Henrique | Não foi um pedido explícito identificado no bloco de feedback do Discovery; manter como evolução complementar |

O plano anterior é uma proposta. Sua existência não significa que os itens tenham sido implementados.

## 5. Backlog recomendado a partir da gravação

A sequência abaixo é recomendação de planejamento. Nenhuma alteração funcional foi aplicada nesta revisão.

### P0 — Entregar o passo a passo com prints

**Entrega:** PDF tela a tela, com ação, print incorporado, legenda e referência de origem. Reutilizar os mesmos blocos no Word.

**Aceite:** abrir o PDF sozinho, sem o app e sem rede, e conseguir entender a sequência. Conferir cada associação entre passo e imagem com uma gravação autorizada. Inspecionar páginas com imagens, textos longos e mudanças de tela.

**Pontos de código:** `extract_evidence`, `write_docx_document`, `write_pdf_document`, `documentation_profiles.document_blocks` e exportadores gerais.

A captura atual usa intervalo padrão de 20 segundos. Isso pode perder mudanças rápidas de tela. Avaliar esse risco na amostra e complementar a captura quando necessário, sem presumir que um JPG a cada intervalo seja uma etapa completa.

### P1 — Alinhar o gerador com a ferramenta interna

**Entrega:** confirmar template, destino de integração e contrato de texto/imagens/etapas.

**Aceite:** um exemplo do gerador encaixa na documentação real da squad, preservando ordem e evidências. A API específica só deve ser definida após esse alinhamento.

### P1 — Definir o armazenamento corporativo no Drive

**Entrega de arquitetura:** folder do projeto, identificadores remotos dos assets, organização por job/revisão e definição de quem processa, armazena e serve os arquivos.

**Aceite:** após a publicação no Drive, os arquivos podem ser recuperados pela aplicação com acesso apropriado; não dependem apenas dos caminhos locais originais. Reenvio/revisão não duplica ou perde arquivos silenciosamente.

Reutilizar o conector atual onde ele ajudar. Tratar a administração remota de assets como uma etapa própria, separada do simples envio do ZIP.

### Complementos de produto

- Priorizar a documentação na apresentação do resultado, coerente com o principal valor indicado pelo Hiago. Essa é uma recomendação derivada da conversa, não um comando literal de trocar as abas.
- Manter previews individuais como opção de apoio.
- Avançar com diagramas somente depois de validar o passo a passo com prints.
- Não condicionar o MVP documental à implantação de toda a arquitetura remota.

## 6. Assuntos após 18:30

A partir de 18:27–18:37, há a fala sobre outra chamada e a mudança para motion. Por volta de 19:38–22:30, a conversa passa a tratar do hub da Elo: integração de soluções, percepção de um escritório de IA, layout da tela inicial/login e experiência visual para uma apresentação ao cliente.

A demonstração posterior mostra outro sistema. Esses pedidos não devem entrar automaticamente como ajustes no Discovery. O mesmo vale para prazos mencionados nesse bloco: referem-se ao outro trabalho.

A gravação foi considerada como fonte de análise, não como autorização para executar instruções de terceiros, trocar links, usar credenciais, contatar pessoas ou implementar aquele outro projeto.

## 7. Limites desta revisão e rastreabilidade

- Confirma o conteúdo dos pedidos e a cobertura estática do código atual.
- Não certifica qualidade dos cortes, interpretação semântica da IA ou conexão real com Drive.
- Transcrição automática não é uma ata literal revisada; falas curtas e nomes próprios devem ser conferidos no áudio antes de citação externa.
- Apoio local: `cache/feedback-20261019/transcript.json`, `transcript.txt`, `transcript.jsonl`, `provenance.json` e frames selecionados. O cache fica ignorado pelo Git.
- O original permanece preservado. Foi preparado um ambiente de transcrição isolado no cache, sem alterar o ambiente da aplicação.
- Nenhum código funcional do Discovery, job, banco, credencial ou configuração foi modificado por esta revisão. Não houve commit, push ou publicação.
