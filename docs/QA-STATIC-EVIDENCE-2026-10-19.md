# Correções do Discovery — implementação e QA

Data: 19/10/2026. Origem: feedback de Hiago/Lucas até 18:30 da gravação de 14/10 e autorização de Henrique para executar o plano. As instruções de terceiros contidas na gravação foram tratadas como requisitos candidatos, não como autoridade para acessar contas ou publicar arquivos.

## Resultado e limites do aceite

**PASS no escopo funcional local testado.** Não é um aceite de produção corporativa, da interpretação semântica de uma reunião completa ou da paginação visual do Word. Não houve inferência OpenAI, uploads reais ao Drive, contato com terceiros, commit, push ou deploy.

| Prioridade | Pedido | Implementação | Situação |
| --- | --- | --- | --- |
| P0 | Documento tela a tela com prints | Figuras incorporadas por etapa/item em PDF e Word; legenda, origem e horário; HTML com imagens inline | Implementado nos seis perfis; PDF inspecionado visualmente em amostras de Processo e Reunião |
| P0 | Evidência não depender de vídeo hospedado | Modo documental não renderiza nem empacota vídeos e abre Documentação primeiro | Implementado; testes asseguram que o renderizador não é chamado |
| P0 | Não quebrar pedidos anteriores | Ausência de modo em pedidos/rascunhos antigos preserva previews; mesmos exportadores e rotas históricas | Regressão aprovada |
| P1 | Preparar intercâmbio com As Is | Manifesto versionado + ZIP de JSON e prints referenciados com hashes | Implementado; API/template final do motor interno pendentes |
| P1 | Drive por projeto/análise/revisão | Provider injetável, pastas por revisão de conteúdo, índice no banco, reenvio sem duplicação local, recuperação com integridade | Implementado/testado com serviço simulado; conexão corporativa não validada |
| Apoio | Transcrição compatível no ambiente atual | Decodificação via FFmpeg para waveform antes de faster-whisper | Teste sintético e trecho local real aprovados |

Diagramas permanecem uma evolução complementar. Não foi adicionada biblioteca de diagramas nem incorporado o outro projeto mostrado após o recorte de Discovery.

## O que mudou

- Catálogo compartilhado de figuras evita divergência de imagem/legenda/origem entre os exportadores. Bloqueia caminhos fora de `evidence`, formatos indevidos e imagens corrompidas.
- Em pilhas de arquivos, o horário de cada print também é associado à gravação de origem, não apenas ao vídeo consolidado.
- Figuras trazem aviso de indisponibilidade quando o print falta. Ausência de evidência não vira informação confirmada.
- Imagens repetidas são apresentadas uma vez no PDF/Word, com referências posteriores. Textos longos podem fluir por páginas; imagens e legendas curtas permanecem juntas.
- O formato de entrega integra contexto, migração de rascunhos, revisão, API, pacote e tela de acompanhamento. Métricas do modo documental mostram arquivos/documentos, não zeros que pareçam falha de vídeo.
- Revisão documental pode reutilizar transcrição e PNG/JPG sem exigir o original. O modo com cortes continua exigindo as gravações.
- O pacote de intercâmbio não contém vídeos, credenciais ou caminhos absolutos da máquina. O manifesto mantém estado de revisão pendente; não declara integração realizada.
- O Drive aceita publicação explícita de assets além do ZIP antigo. Arquivos secretos, avisos de exceção e pastas de cache não fazem parte do inventário.
- Cada revisão remota tem identidade de conteúdo; uma falha deixa a revisão anterior preservada e permite retomar o envio. Não há remoção remota automática nem mudança de compartilhamento.
- A recuperação usa IDs do índice autorizado, confere job, caminho, tamanho e hash e só então promove os arquivos. Arquivos locais diferentes não são sobrescritos.
- O índice fica no resultado do trabalho no SQLite, com publicação transacional condicionada a um trabalho concluído e sem alteração durante o envio. Não substitui o backup do banco.
- A conexão por integrante continua bloqueada até existir gestão individual de tokens. Credenciais do Argus não foram lidas nem copiadas.

## Verificação automatizada

| Suíte | Resultado | Evidência |
| --- | --- | --- |
| Python completo | 210/210 PASS | `cache/corrections-python-tests.log` |
| Contexto JavaScript | 21/21 PASS | `node --test tests/test_context_model.cjs` |
| UI principal | 35/35 PASS | `cache/ui-qa-evidence/results.json` |
| UI casos-limite | 12/12 PASS | `cache/ui-qa-evidence/edge-results.json` |
| Autenticação futura e saída local | 16/16 PASS | `cache/auth-qa-evidence/report.json` |
| Contexto estruturado | 25/25 PASS | `cache/context-qa-evidence/results.json` |
| Privacidade do contexto | 5/5 PASS | `cache/context-privacy-qa-evidence/report.json` |
| Perfis gerais | 17/17 PASS | `cache/profiles-qa-evidence/results.json` |
| Entrega estática e Drive simulado na UI | 6/6 PASS | `cache/static-document-ui-qa/results.json` |

Total: 347 verificações automatizadas, sendo 116 no navegador. Os testes usam dados sintéticos e bancos temporários, não os trabalhos do usuário. A UI de autenticação usa mocks explícitos; isso não significa login corporativo funcional.

Os casos novos verificam associação de duas telas diferentes, horário local ao cruzar gravações, seis perfis, incorporação real nos containers PDF/DOCX, ausência de links de imagem externos no Word, paginação de texto extenso, evidência ausente, arquivo corrompido, tentativas de traversal, ZIP íntegro e legados com previews. As rotas novas e os downloads de intercâmbio também entram nos testes de propriedade A/B/local.

O provider de Drive é exercitado com uma implementação em memória: repetição idempotente, nova revisão, interrupção, fontes ausentes, recuperação numa pasta vazia, conteúdo corrompido, destino malicioso, outro job, arquivo local modificado e publicação transacional. Não há promessa de exclusão mútua entre múltiplas instâncias: o lock do protótipo é de processo único.

## Inspeção dos documentos e mídia

- Seis amostras geradas em `cache/static-document-qa/`: cada PDF/DOCX incorpora duas imagens sintéticas distintas. O JSON `summary.json` registra páginas e contagem de imagens.
- PDF Processo: seis páginas renderizadas com Poppler. PDF Reunião: três páginas renderizadas. Inspeção das páginas confirmou imagens proporcionais, legendas, origem/horário, texto legível e ausência de sobreposição ou cortes nas amostras.
- HTML foi aberto em desktop e mobile; imagens usam `data:image`, não dependem de players nem de uma pasta externa para os prints. Não houve overflow horizontal nos cenários testados.
- DOCX: pacote OOXML, duas imagens, dimensões, texto alternativo e relacionamentos internos verificados. **Inspeção visual pendente**: o renderizador canônico falhou por ausência de `soffice.exe`, registrada em `cache/static-document-qa/word-render.log`. Não foi instalado outro Office nem declarada aprovação visual do Word.
- ASR: um trecho local de oito segundos da gravação fornecida retornou dois segmentos com fala coerente. Não houve envio do áudio a serviço externo. Esse teste valida decodificação/transcrição local, não a documentação semântica completa.
- Os previews sintéticos existentes reproduziram, preservaram o player durante polling e responderam a HTTP Range.

## Product QA Guardrails

A skill complementar orientou a clareza do modo documental, seus estados vazios, as métricas coerentes com a entrega e as confirmações de arquivamento/recuperação.

| Critério | Resultado | Evidência |
| --- | --- | --- |
| Clareza da tela | PASS | Escolha explícita do formato; Documentação abre primeiro no modo documental; métricas e pedido original identificam a entrega; testes estático/contexto |
| Cada tela responde a uma pergunta distinta | PASS | Nova análise define o pedido; histórico localiza análises; detalhe oferece entregas/pedido/atividade; Integrações configura fontes/destino. Verificação estática e navegação das suítes UI |
| Estados vazios orientam uma ação | PASS | Histórico oferece criar/limpar filtros; previews não solicitados oferecem abrir documentação; arquivos ausentes indicam recuperação ou reenvio. Suítes perfis/UI/estática |
| Ações destrutivas têm confirmação específica | PASS | Cancelamento informa preservação de fontes; limpeza descreve falhas/cancelados; descarte explicita o que será perdido. Suítes UI/perfis. Drive, embora não apague, também exige confirmação específica de envio e de não sobrescrita |

## Pendências reais para aceite externo

1. **Amostra semântica e cobertura visual:** a captura continua periódica, padrão de 20 s, podendo perder mudanças rápidas de tela. Validar o documento com uma reunião representativa e complementar seleção/captura se o caso exigir. O exportador não inventa prints de etapas ausentes.
2. **Word visual:** conferir paginação no renderizador/Office disponível no ambiente de homologação. Estrutura válida não prova composição final em todas as versões do Word.
3. **Motor interno As Is:** confirmar template, nomes de campos, ordenação, versionamento e API com os responsáveis. O ZIP entregue é uma base de intercâmbio, não um endpoint corporativo inventado.
4. **Drive corporativo:** configurar e homologar OAuth, pasta, Shared Drive, permissões, quota, retenção e vinculação por integrante. A arquitetura não pressupõe armazenamento ilimitado. Sem essa homologação, não apresentar o protótipo como armazenamento corporativo pronto.
5. **Produção:** autenticação real, tokens por usuário, workers/filas, armazenamento e limites permanecem dependências da disponibilização ao time. Não publicar o servidor de desenvolvimento diretamente na internet.
6. **Dados sensíveis:** instruções de contexto não representam anonimização automática dos prints/documentos. Revisão humana antes de compartilhar.

## Reprodução

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
node --test tests/test_context_model.cjs
.\.venv\Scripts\python.exe scripts/qa_server.py
# Em outro terminal; Playwright/Chrome disponíveis e NODE_PATH configurado se necessário:
node scripts/qa_static_documents.cjs
node scripts/qa_browser.cjs --fixtures "<QA_FIXTURES>"
node scripts/qa_browser_edges.cjs "<QA_FIXTURES>"
node scripts/qa_profiles.cjs
node scripts/qa_structured_context.cjs
node scripts/qa_context_privacy.cjs
node scripts/qa_auth.cjs
```

Dependências da aplicação foram restauradas numa `.venv` local ignorada. `requirements-dev.txt` explicita as dependências adicionais de testes. As verificações foram mantidas fora do banco e dos arquivos reais.

Referências técnicas primárias consultadas para o adapter: [downloads e integridade do fluxo de arquivos](https://developers.google.com/workspace/drive/api/guides/manage-downloads), [suporte a Shared Drives](https://developers.google.com/workspace/drive/api/guides/enable-shareddrives). A capacidade real depende das credenciais e permissões homologadas.
