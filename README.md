# Btime Discovery

Aplicativo local para transformar gravações em documentos para diferentes áreas, cruzando transcrição, evidências visuais e o contexto de cada pedido. O pacote Python e os caminhos históricos mantêm o nome `rpa_docs` por compatibilidade.

O provedor padrão de IA é agora o **Lovable**. Este repositório ainda executa o worker Python, SQLite e arquivos locais; configurar o gateway não migra dados nem publica esse worker no Lovable Cloud. A separação entre as duas partes está em [Integração com Lovable](docs/LOVABLE-INTEGRATION.md).

## Continuidade entre IAs — leia primeiro

Atualizado em **26/11/2026** por conferência do checkout, do histórico Git, da documentação e das decisões desta conversa. Este README é o ponto de entrada para continuar o projeto em outra IA. As datas dos testes abaixo são históricas; esta atualização documental não executou novamente o app, chamadas de IA ou testes de produção.

| Referência | Estado verificado / conhecido |
| --- | --- |
| Produto | **Btime Discovery**, anteriormente Btime RPA Docs. Mensagem de apresentação: **Transforme gravações em documentos**. |
| Repositório local em uso | `G:\Repositorios\btime-rpa-docs` |
| Remoto principal configurado | `https://github.com/henriquecunha-byte/rpadiscovery.git` |
| Branch local | `main` |
| HEAD local verificado em 26/11 | `1c86ded47c368673815dc805c668f4d852988368`, de 29/10/2026, antes desta atualização do README. |
| Checkpoint anterior a este handoff | `1c86ded`, enviado à `main` em 29/10. Fetch em 26/11 confirmou HEAD e `origin/main` alinhados nesse commit antes do commit desta documentação. |
| Conta GitHub indicada pelo usuário | `henriquecunha-byte`. Verificar a conta antes de publicar; houve confusão com a conta pessoal no histórico. |
| Remoto histórico | `legacy` aponta para `hvrcdesign242307/btime-rpa-docs`; não é o destino principal atual. |
| App publicado | O usuário informou uso de **Lovable AI e Lovable Cloud**. O ID/link do projeto no editor não foi identificado nesta conversa. |
| Integração no Lovable | **Não confirmada**: o código local e um push no GitHub não comprovam que a interface, o login ou as exportações foram atualizados no app publicado. |

**Há dois ambientes distintos.** Este checkout executa Python/FastAPI, SQLite, FFmpeg, transcrição e arquivos locais. O app Lovable informado pelo usuário tem sua própria configuração de API e banco. Preservar essa configuração ao adaptar funcionalidades; não substituir o Cloud pelo backend local. A seleção do gateway de IA neste Python não representa uma migração para o Cloud.

Em 29/10, o conector Lovable disponível listava projetos pessoais e da Ventiur, sem o Discovery da Btime. O repositório informado continha somente a branch `main`, sem um vínculo de publicação identificado nessa verificação. O navegador integrado também falhou ao conectar naquela sessão. Essas são observações históricas, não impedimentos permanentes: verificar os acessos atuais antes de pedir novamente informações ao usuário.

## Decisões de produto e restrições para continuidade

1. **Atender várias áreas.** Não restringir o produto a RPA, Vivo ou Trevo. São exemplos históricos de reuniões, não presets obrigatórios.
2. **Contexto por pedido.** Perfil, objetivo, público, sistemas, checklist e guia orientam a análise. Preservar escolhas e edições manuais do usuário.
3. **Documentação estruturada.** Entregar síntese organizada e evidências relacionadas às etapas; a transcrição bruta é um material separado.
4. **Prioridade ao que é falado nos cortes.** Preservar blocos completos sobre o assunto, incluindo perguntas, respostas, exemplos e contrapontos. Não impor redução percentual ou duração final artificial.
5. **Passo a passo com prints.** Para o cenário de processo, o PDF deve explicar a sequência tela a tela, com imagens reais incorporadas. Vídeo é complemento, não dependência para entender o documento.
6. **Vídeos opcionais e individuais.** Novos pedidos começam em documentação com prints. Quando o usuário pedir vídeos com cortes, entregar um preview separado por gravação, além dos demais materiais.
7. **Privacidade por conta.** Gravações, contexto, transcrições, imagens, previews, documentos e ZIP seguem o mesmo proprietário. Um usuário não deve acessar conteúdo de outro por lista, link direto ou ação na API.
8. **Preservar a infraestrutura do app Lovable.** Manter a API de IA e o banco existentes; não trocar chaves, provedor, projeto Cloud ou armazenamento ao portar ajustes de interface. A instrução do usuário é não usar a skill do Supabase neste projeto.
9. **Fidelidade às fontes.** Não inventar nomes de participantes, regras, cliques, campos ou imagens ausentes. Orientação para dados sensíveis não equivale a anonimização automática.
10. **Fontes preservadas.** Nunca modificar a gravação original, reprocessar trabalhos ao simplesmente abrir uma tela, atribuir legados ao primeiro login ou apagar dados antigos para resolver testes.

## Histórico consolidado do trabalho

As datas de execução dos relatórios podem anteceder o commit que consolidou o trabalho. Os registros abaixo distinguem implementação, planejamento e especificação.

| Período | O que foi feito | Referência |
| --- | --- | --- |
| Agosto/2026 | Adaptação do fluxo de análise/cortes usado no canal para discovery de processos: entrada de vídeos, contexto, evidências e entregáveis prontos, sem exigir DaVinci Resolve. | Commit inicial `8104412` e evolução posterior. |
| 24/08 | Otimizações de reuniões, paralelismo, correção de reprodução do preview, limpeza de falhas/cancelados, documentos estruturados e cortes com prioridade à fala. | `8ff0836`, `18888b0`, `1fd3b98`, `f3516ed`, `a25c6a0`, `c6d0681`, `81876cf`. |
| 24/08–01/09 | Pilha incremental e previews separados por arquivo; guia gerado para o pedido e cortes revisitáveis. | `b470cab`, `964d32a`. |
| 08/10 | Rodada de QA e refinamento, identidade Btime, fila/revisão, uploads e ZIP, validações, contexto estruturado, base visual de login e autorização por proprietário. | `87960dc`; relatórios de QA, contexto, autenticação e privacidade em `docs/`. |
| 14/10 | Generalização para seis perfis, contratos de documentação por área e planejamento de PDF estático com evidências para o cenário As Is. | [Perfis](docs/MULTI-AREA-PLAN.md) e [plano As Is](docs/PLAN-ASIS-STATIC-DOCUMENTATION.md). |
| 14/10 | Apresentação a Hiago/Lucas; prioridade explicitada para prints e passo a passo tela a tela. Sugestão de Drive corporativo veio na discussão técnica com Lucas. | [Registro do feedback](docs/FEEDBACK-DISCOVERY-2026-10-14.md). |
| 19/10 | PDF/Word/HTML com imagens, modo documental, pacote de intercâmbio, arquivamento/recuperação no Drive com testes simulados e leitor completo de documentos dentro do app. | [QA de evidências estáticas](docs/QA-STATIC-EVIDENCE-2026-10-19.md) e [leitor integrado](docs/QA-INLINE-DOCUMENTATION-2026-10-19.md). |
| 28/10 | Consolidação das melhorias e seleção explícita do gateway Lovable no Python, sem fallback para a chave OpenAI antiga. | `4bacff0`, `38298d3`; [contrato e limites](docs/LOVABLE-INTEGRATION.md). |
| 29/10 | Análise da gravação para recuperar o fluxo demonstrado; exportação reutilizável de contexto/revisão; correção de mensagens de erro que permaneciam após seleção automática de etapa/checklist. Commit e push concluídos. | `1c86ded`; [mapeamento e QA](docs/RECONSTRUCAO-DISCOVERY-2026-10-29.md). |
| 29/10 | Criados dois documentos para o usuário encaminhar ao Lovable: pedidos do Hiago e guia de login/contas. São especificações, não prova de aplicação no Cloud. | [Pedidos do Hiago](docs/PEDIDOS-HIAGO-LOVABLE.md) e [login/contas](docs/GUIA-LOGIN-CONTAS-LOVABLE.md). |
| 26/11 | Consolidado este handoff no README e incluídas cópias dos dois guias no repositório, preservando os originais do OneDrive. | Atualização apenas documental; não altera comportamento, API ou banco. |

O histórico também inclui um pedido de vídeo demonstrativo com trilha, sem narração, e a frase “Transforme gravações em documentos”. A entrega audiovisual final não foi localizada/verificada neste checkout durante este handoff; não confundir esse material de apresentação com os previews gerados pelo produto.

## Estado real por área

| Área | Implementação neste checkout | O que ainda exige confirmação |
| --- | --- | --- |
| Upload e pilha | Vídeo, pasta, ZIP, adição incremental e fontes do Drive por conector. | Fluxo real equivalente no app Lovable; permissões e limites do ambiente. |
| Contexto e revisão | Seis perfis, checklist, públicos, sistemas, dados sensíveis, guia gerado/manual e revisão. Exportação reutilizável pronta. | Portar para o frontend efetivamente publicado sem duplicar estado ou serviços. |
| Cortes | Seleção contextual guiada pela fala; previews individuais e HTTP Range. | Qualidade semântica e tempo com gravações representativas. |
| Documentação | Estrutura por perfil, prints incorporados, leitura dentro do app e exportação. | Aceite real tela a tela; mudanças rápidas podem escapar à amostragem de imagens. |
| PDF e Word | Geração real testada com material sintético; PDF inspecionado nas amostras registradas. | Inspeção visual completa do Word e de documentos de reuniões reais. |
| IA | Adaptador Lovable padrão com contratos testados por HTTP simulado. | Credencial, disponibilidade do modelo, saldo e operação real no ambiente de destino. |
| Banco | SQLite local e propriedade por trabalho. | Estrutura atual do Cloud ainda não inspecionada nesta conversa; não importar SQLite como substituto. |
| Login | Telas e contrato preparados; provedor real local ainda não implementado. | Login funcional e isolamento fim a fim com duas contas no projeto publicado. |
| Drive | Importação, envio de pacote, arquivamento de assets e recuperação por índice/hashes. | OAuth e permissões reais; tokens por integrante. A conexão local é bloqueada para contas autenticadas. |
| Ferramenta interna As Is | Plano e pacote versionado de intercâmbio com imagens. | Confirmar destino, template, contrato e responsáveis; integração direta não implementada. |

### O que Hiago pediu e como avaliar

O ponto principal da reunião foi **documentação com prints e descrição do passo a passo tela a tela**. Na versão demonstrada, o PDF não continha as imagens. A implementação local posterior de 19/10 corrigiu a composição estática, mas isso não comprova o resultado no Lovable nem a cobertura de todas as telas de uma reunião real.

Para aceitar a entrega, abrir o PDF baixado sem rede e conferir a sequência de ações, a correspondência de cada print e a legibilidade das páginas. A imagem deve mostrar a evidência da ação; quando uma etapa tiver sido apenas narrada, declarar a ausência visual. Word com imagens é a extensão de consistência dos formatos existentes; o problema explícito na reunião foi o PDF.

O relato de 19/10 em `FEEDBACK-DISCOVERY-2026-10-14.md` descreve o diagnóstico **anterior** à implementação. Consultar depois `QA-STATIC-EVIDENCE-2026-10-19.md`; não interpretar os “pendentes” históricos isoladamente como o estado atual de todo o código.

## Guias portáveis para enviar a outra IA

- [PEDIDOS-HIAGO-LOVABLE.md](docs/PEDIDOS-HIAGO-LOVABLE.md): feedback com horários aproximados, implementação proposta e critérios de aceite documental.
- [GUIA-LOGIN-CONTAS-LOVABLE.md](docs/GUIA-LOGIN-CONTAS-LOVABLE.md): login, admissão de integrantes, propriedade, downloads privados, legados, worker e testes A/B.
- [Interface reutilizável de contexto](integrations/context-ui/README.md): geração e contrato do formulário independente de backend. O evento `discovery:requestready` atua no mesmo documento; não há integração automática com React ou iframe.

Os dois Markdown foram originalmente entregues em `E:\OneDrive\#DESIGN\2 - BTIME\`. As cópias em `docs/` permitem continuar pelo repositório sem depender desse caminho. Se forem revisadas separadamente em outra IA, comparar as versões antes de consolidar mudanças; não presumir sincronização automática entre cópias ou com a nuvem.

### Materiais de referência

- Gravação fornecida pelo usuário: `C:\Users\Henrique\Downloads\Ferramenta de Discovery - 2026_10_14 15_31 GMT-03_00 - Recording.mp4`. A duração é de aproximadamente 28min30s; o bloco relevante ao Discovery vai até cerca de 18min30s. O restante trata de outro projeto/motion.
- A análise de 29/10 usou capturas periódicas e transcrição local até 19min28s. Evidências e transcrições ficaram em `cache/meeting-reconstruction-20261029/`, fora do Git. Nomes próprios e locutores não têm identificação automática confiável.
- Os pacotes de design e motion Btime foram fornecidos em `E:\OneDrive\#DESIGN\2 - BTIME\#Marca\Brandbook 2026\`. O que foi aplicado está registrado em [BRAND-IMPLEMENTATION.md](docs/BRAND-IMPLEMENTATION.md).
- O usuário sugeriu [diagram-design](https://github.com/cathrynlavery/diagram-design) como referência futura. Isso não é uma dependência instalada nem um requisito anterior ao PDF com prints.
- Repositórios mencionados anteriormente, como `Btime/blank-canvas-pages`, não substituem o destino principal acima sem nova confirmação. A vinculação ao Lovable não foi provada pelo endereço do GitHub.

## Mapa técnico para localizar alterações

| Arquivo / diretório | Responsabilidade |
| --- | --- |
| `rpa_docs/api.py`, `schemas.py` | Rotas, contratos, upload, ações e respostas. |
| `rpa_docs/database.py`, `orchestrator.py` | SQLite, ciclo de trabalhos, fila, retomada, cancelamento e worker. |
| `rpa_docs/pipeline.py` | Preparação de mídia, transcrição, evidências, síntese, cortes e pacote. |
| `rpa_docs/ai.py`, `errors.py`, `config.py` | Provedor, cliente de IA, erros seguros, configuração e caminhos. |
| `rpa_docs/context_model.py` | Normalização, compatibilidade e guia no backend. |
| `rpa_docs/static/context-rules.json` | Regras compartilhadas dos seis perfis e entregáveis. |
| `rpa_docs/static/context-model.js`, `context-form.js` | Modelo, estado, geração do guia e validação do formulário. |
| `rpa_docs/documentation_profiles.py`, `evidence_documents.py` | Conteúdo por perfil e composição das evidências nas exportações. |
| `rpa_docs/documentation_reader.py` | Leitura/versionamento do documento salvo e exportações coerentes com o snapshot. |
| `rpa_docs/static/documentation-reader.js` e `.css` | Leitor de documentação dentro do app. |
| `rpa_docs/auth.py`, `access.py` | Base de autenticação e autorização por proprietário. |
| `rpa_docs/uploads.py` | Validação e organização de arquivos recebidos. |
| `rpa_docs/drive.py`, `drive_storage.py` | Conexão, importação, publicação, arquivamento e recuperação no Drive. |
| `rpa_docs/static/index.html`, `app.js`, arquivos CSS | Interface nativa, navegação e estados do aplicativo. |
| `integrations/context-ui/`, `scripts/export_context_ui.py` | Referência exportável de contexto/revisão, gerada dos arquivos canônicos. |
| `tests/`, `scripts/qa_*.py`, `scripts/qa_*.cjs` | Testes Python/JS e cenários de navegador. |

O frontend deste checkout é HTML/CSS/JavaScript nativo; não assumir que existe um projeto React/Vite ou um comando `npm run dev` na raiz. Os perfis selecionam contratos de documentação, não seis agentes autônomos. O processamento pesado usa FFmpeg/FFprobe e Faster-Whisper no servidor local.

## Próximos passos, na ordem recomendada

1. **Identificar a versão que será alterada.** Conferir checkout, branch, `git status` e mudanças de outra IA. Para trabalhar no app Lovable, obter o projeto efetivamente conectado e inspecionar sua implementação e acesso atuais.
2. **Aplicar contexto/checklists no app de destino.** Reaproveitar as regras atuais e adaptar os componentes ao frontend existente, preservando API, banco, autenticação e estado do pedido. Não substituir o app por um preview isolado.
3. **Validar o pedido documental do Hiago.** Usar uma reunião autorizada, conferir texto e imagens tela a tela, exportar PDF e verificar offline. A amostragem periódica pode exigir captura complementar; não inventar evidências ausentes.
4. **Implementar ou concluir contas reais no ambiente atual.** Seguir o guia de login, proteger todas as rotas/arquivos e validar A/B. Manter os legados sem proprietário fora da atribuição automática.
5. **Homologar integrações que forem necessárias.** Drive por identidade e integração As Is dependem de configuração e contratos concretos. A existência dos adapters locais não comprova integração corporativa.
6. **Registrar o resultado.** Atualizar este README e o relatório da rodada com arquivos alterados, evidências, limitações, commit e publicação efetivamente realizados.

Nenhum desses itens deve ser marcado como concluído apenas por existir um plano, uma tela, uma chave configurada, um teste com mocks ou um push no GitHub.

## Verificações históricas e limites

Os números abaixo pertencem a rodadas distintas e podem incluir regressões repetidas; **não somar como testes únicos**. Não foram reexecutados em 26/11 durante este handoff.

| Rodada | Resultado registrado | Limite principal |
| --- | --- | --- |
| 14/10 — múltiplas áreas | Python: 187 PASS, 1 SKIP; JS: 19 PASS; navegador e pipeline conforme relatório. | IA simulada; sem aceite semântico de reunião real. [Relatório](docs/MULTI-AREA-PLAN.md). |
| 19/10 — evidências estáticas | 347 verificações automatizadas, incluindo 116 no navegador. PDF inspecionado nas amostras; imagens do DOCX verificadas estruturalmente. | OAuth/Drive simulados; Word sem inspeção visual completa. [Relatório](docs/QA-STATIC-EVIDENCE-2026-10-19.md). |
| 19/10 — leitor integrado | Python: 220 PASS; leitor: 24 PASS; JS: 21 PASS; demais regressões no relatório. | Material de demonstração/sintético; não valida integração Cloud. [Relatório](docs/QA-INLINE-DOCUMENTATION-2026-10-19.md). |
| 28/10 — gateway Lovable | Python: 232 PASS; JS: 21 PASS. Contratos com transporte HTTP simulado. | Nenhuma validação real de chave, saldo ou modelo no Cloud. [Relatório](docs/QA-LOVABLE-INTEGRATION-2026-10-28.md). |
| 29/10 — recuperação do contexto | 26 cenários do app, 10 da referência exportada e 21 testes JS: 57 verificações aprovadas. | Formulário/revisão locais; não geração documental no app publicado. [Relatório](docs/RECONSTRUCAO-DISCOVERY-2026-10-29.md). |

Há registros antigos de análises cujas fontes/entregas não acompanhavam o checkout durante os QAs. As contagens nos relatórios são fotografias daquelas datas, não um inventário atual. Se houver histórico sem arquivo, orientar recuperação ou reenvio; não apagar o registro, fabricar a entrega ou interpretar ausência de mídia como falha de seleção contextual.

### Regras de trabalho para a próxima IA

- Ler este README, o documento específico da área e o código antes de alterar. Relatórios antigos descrevem o estado da respectiva rodada; planos não são comprovação de implementação.
- Respeitar alterações locais feitas por outras IAs. Não usar reset, limpeza de arquivos ou sobrescrita indiscriminada para sincronizar.
- Não incluir `.env`, tokens, transcrições reais, gravações, bancos, `jobs/`, `cache/` ou históricos privados de IA em commits, anexos públicos ou logs. A lista de arquivos preparada para commit precisa ser conferida.
- Usar a identidade GitHub correta. Não trocar a conta global, o modelo ativo, credenciais ou limites de gastos por conta própria.
- Aplicar as instruções atuais do `AGENTS.md` do ambiente. Nos QAs, carregar `product-qa-guardrails` e o guia FAST e registrar os cinco critérios: clareza, telas redundantes, vazios acionáveis, confirmações destrutivas específicas e complexidade proporcional. Usar PASS/FAIL com evidência, N/A ou NOT RUN conforme o caso.
- Aplicar `codex-budget-guardian` e `delivery-location` quando disponíveis. Código e documentação do projeto permanecem no repositório em uso; entregas separadas seguem o destino confirmado pelo usuário.
- Para imagens e vídeos a partir de imagens, a regra atual do usuário exige a skill `imagegen-magnific-video`, arte no ImageGen, apresentação dos quadros e aprovação antes de animar no Magnific. Consultar a versão vigente dessas instruções quando houver uma tarefa audiovisual.
- Testar proporcionalmente à alteração. Identificar o que foi simulado e o que foi executado com serviços reais; não repetir chamadas pagas ou reprocessar reuniões sem necessidade.
- Ao encerrar, registrar o estado de commit/push/deploy e atualizar as pendências. Não afirmar que um servidor continua aberto ou que o app está publicado sem conferir naquela sessão.

### Prompt curto para iniciar em outra IA

> Continue o Btime Discovery a partir deste README e do estado atual do repositório. Primeiro confira branch, alterações locais e a documentação da área. Preserve a API e o banco do app Lovable que já existem; o Python/SQLite deste checkout é uma implementação local distinta. O objetivo é atender várias áreas, gerar documentação com evidências e manter gravações/entregas privadas por conta. Não trate testes simulados como aceite de produção. Execute somente o próximo pedido explícito do usuário, valide o escopo alterado e atualize o handoff com o que foi implementado, testado e permaneceu pendente.

## Funcionalidades

- fila local de trabalhos e histórico em SQLite;
- prompt de contexto gerado automaticamente a partir do pedido e da pilha de arquivos, já no formato que a ferramenta usa para analisar, documentar e cortar;
- upload por arrastar e soltar de vídeos, pastas inteiras ou ZIPs;
- pilha visível de arquivos, com adição incremental e remoção individual antes do processamento;
- consolidação automática de várias gravações, sem depender de editor externo;
- captura de evidências visuais com timecode;
- captura paralela e pontual de evidências com FFmpeg, sem decodificar a gravação inteira;
- transcrição local otimizada para reuniões com Faster-Whisper;
- descrição visual baseada somente em evidências observáveis;
- preview MP4 com os trechos relevantes e cortes conservadores;
- seleção contextual dos cortes pela API: todo bloco falado relacionado ao assunto pedido permanece, sem meta artificial de duração; os frames servem como confirmação visual;
- um preview cortado e um roteiro de cortes para cada vídeo da pilha, disponíveis separadamente na tela e dentro do ZIP final;
- tratamento de participantes por papel operacional, sem atribuir nomes quando o áudio não possui identificação confiável de locutor;
- relatório HTML navegável e JSON estruturado por trabalho;
- matriz de evidências que reproduz o corte em que o assunto é falado, a partir do print e sem sair do relatório;
- seis perfis de documentação: Personalizado, Reunião, Treinamento, Entrevista, Pesquisa e Processo / RPA;
- documentos gerais com temas, decisões, próximos passos, aprendizados, perguntas/respostas, achados ou recomendações, conforme o perfil e os entregáveis escolhidos;
- documentação de Processo / RPA com fluxo, atores, sistemas, regras, exceções e requisitos de automação, sem impor essas seções aos demais perfis;
- Word editável, PDF, HTML, Markdown, JSON e matriz de evidências separados da transcrição bruta;
- documentação completa com prints legível dentro do app, com índice de seções, PDF sob demanda e ZIP complementar;
- pacote ZIP com relatório, preview, prints, transcrição, PDF e dados estruturados;
- conexão opcional com Google Drive por OAuth e envio do pacote para uma pasta compartilhada;
- orçamento de referência (não é um teto automático de cobrança) e autorização explícita por execução;
- diretório separado para cada análise em `jobs/<id>` e autorização por proprietário preparada; o modo local não autentica integrantes da equipe;
- cancelamento de trabalhos na fila ou em processamento, preservando os arquivos já recebidos;
- retomada de trabalhos com falha ou cancelados sem repetir o upload;
- acompanhamento com tempo decorrido, etapa, posição na fila e previsão restante baseada no ritmo atual e no histórico;
- resumo permanente do guia, público e nível de detalhe de cada pedido;
- limpeza em lote de trabalhos cancelados ou com falha, incluindo seus arquivos locais, mediante confirmação;

## Princípios

- A gravação original nunca é alterada.
- Cada descrição aponta para um print e um momento da gravação.
- A análise deve declarar incerteza e não inferir cliques ou valores invisíveis.
- As credenciais ficam apenas no ambiente do servidor; o `.env` local é ignorado pelo Git. No Lovable Cloud, a credencial do projeto é gerenciada como segredo.
- O JSON intermediário sustenta as exportações em Word, PDF e template Btime.

## Execução

```powershell
.\setup.ps1
.\start.ps1
```

O painel abre em `http://127.0.0.1:8770`.

O `setup.ps1` cria a virtualenv Python 3.12 e instala `requirements.txt`. FFmpeg e FFprobe também precisam estar disponíveis, por PATH ou configuração do servidor. Não refaça o setup quando bastar usar a virtualenv existente. Configure segredos somente no ambiente local apropriado; este README não contém chaves.

Para iniciar sem abrir o navegador ou usar uma porta alternativa, a partir da raiz do repositório:

```powershell
.\.venv\Scripts\python.exe -m uvicorn rpa_docs.api:app --host 127.0.0.1 --port 8771
```

Conferir a disponibilidade da porta e o estado de trabalhos ativos antes de encerrar ou reiniciar uma instância. Os endereços documentados não significam que há um servidor ativo agora.

### Preview independente de contexto

```powershell
.\.venv\Scripts\python.exe scripts\export_context_ui.py
.\.venv\Scripts\python.exe -m http.server 8773 --bind 127.0.0.1 --directory cache\context-ui-preview
```

Abrir `http://127.0.0.1:8773/?perfil=processo` para o caminho demonstrado na reunião. Esse preview só exerce contexto e revisão: não autentica, não recebe gravações e não gera documentos ou cortes.

## Login e acesso da equipe no checkout local

A base de login e recuperação está criada, mas permanece **inativa até a integração real com o Supabase**. A entrada inicial oferece **Continuar no ambiente local**, explicitamente sem autenticação. O botão **Sair do modo local** limpa a interface e os rascunhos deste app no navegador, sem cancelar análises no servidor.

`AUTH_MODE=local` preserva os testes atuais. `AUTH_MODE=required` bloqueia a API enquanto o provedor não estiver implementado. Preencher as variáveis do Supabase não ativa o login sozinho. Consulte o contrato, limitações e próximos passos em [docs/AUTH-FOUNDATION.md](docs/AUTH-FOUNDATION.md).

O isolamento por proprietário já está implementado no SQLite e nas rotas: uma conta só poderá acessar suas análises, vídeos, cortes e documentos, inclusive por links diretos. O modo local só vê trabalhos legados/locais sem proprietário; não há associação automática ao primeiro login. A autenticação real continua pendente. [Privacidade por conta e integração futura](docs/USER-PRIVACY.md).

## Contexto personalizado por pedido

### Fluxo apresentado na reunião de 14/10

Para reproduzir o caminho mostrado ao Hiago, selecione **Processo / RPA** em **Tipo de documentação**. Esse perfil exibe soluções, etapa de destino e o checklist de entregáveis. Reunião, Treinamento, Entrevista, Pesquisa e Personalizado usam seus próprios itens; não exigem preencher um projeto de automação.

Há uma [referência funcional somente da interface](integrations/context-ui/README.md) para reaplicar categorização, checklist, guia e revisão no frontend existente, preservando API e banco. Ela é gerada dos mesmos arquivos do app. O [mapeamento da gravação e QA](docs/RECONSTRUCAO-DISCOVERY-2026-10-29.md) registra o que foi apresentado, as melhorias posteriores mantidas e os limites da integração.

Na etapa **Contexto**, escolha o tipo de documentação. Novos pedidos começam em **Personalizado**; **Área ou projeto** é opcional nos perfis gerais. Cliente, solução e etapa técnica aparecem no perfil **Processo / RPA**. O público, o objetivo, os entregáveis e o guia continuam personalizados por pedido.

O botão **Melhorar com IA** usa o contexto e o guia atual. O pedido orienta a organização do conteúdo e os trechos que ficam nos previews: ideias completas e falas relevantes são preservadas, sem meta artificial de duração. Trocar de perfil preserva o guia editado manualmente e sinaliza que ele deve ser revisado. Rascunhos e análises antigos sem perfil permanecem em Processo / RPA.

Os perfis gerais exportam `documentacao.docx`, `documentacao.pdf` e `documentacao.json`, além do Markdown correspondente ao perfil. Não geram requisitos de RPA. Trabalhos antigos mantêm os arquivos e links anteriores. Consulte o [plano, contratos e QA multiarea](docs/MULTI-AREA-PLAN.md).

Sem a credencial do provedor selecionado, **Melhorar com IA** informa a indisponibilidade e preserva o guia atual. O texto continua editável. No padrão `AI_PROVIDER=lovable`, somente `LOVABLE_API_KEY` habilita as chamadas; uma chave antiga da OpenAI não é utilizada automaticamente.

Falhas da IA aparecem como avisos legíveis, sem incluir a chave nem a resposta técnica bruta do provedor. Após alterar o `.env`, reinicie o servidor para carregar a nova configuração.

O modelo é definido por `LOVABLE_MODEL` (padrão `openai/gpt-5.6-luna`, preservando a família antes utilizada). O nome do modelo não muda o faturamento: as chamadas são feitas pelo gateway Lovable. O modo direto legado exige `AI_PROVIDER=openai` explícito e usa `OPENAI_API_KEY` e `OPENAI_MODEL`. Não há troca automática de provedor em caso de erro ou falta de créditos.

Esses nomes são os valores padrão encontrados no código, não uma garantia de disponibilidade atual no catálogo do provedor. O modelo da IA usada para editar este projeto também não altera automaticamente o modelo configurado no aplicativo. A validade da credencial e o funcionamento real do gateway não foram conferidos nesta atualização documental.

## Downloads da entrega

Com o trabalho concluído, **Vídeos e cortes** oferece um player e um download por gravação, com o roteiro dos trechos mantidos. A aba **Documentação** mostra o documento completo diretamente no app: texto, etapas e prints, com um índice de seções. Não é necessário abrir um PDF ou baixar arquivos para ler.

**Exportar PDF** gera uma cópia do documento aberto, com as mesmas evidências. **Baixar ZIP** reúne os formatos disponíveis da análise: Word editável, PDF, HTML, Markdown, JSON, matriz de evidências, prints e vídeos quando solicitados. A lista de formatos fica recolhida, sem substituir a leitura por cartões de download.

Leitura e exportação não chamam IA nem reprocessam as gravações. As rotas verificam o proprietário e a versão salva; se o documento ou uma imagem mudar, a exportação antiga pede uma atualização da leitura. Um pacote incompatível é recusado e deve ser revisado pela ação própria da análise. Consulte [QA do leitor integrado](docs/QA-INLINE-DOCUMENTATION-2026-10-19.md).

Quando a transcrição ou a síntese estiver indisponível, a entrega declara a limitação. Não são criados cortes supostamente contextuais apenas a partir de prints. Documentos e inferências precisam da revisão de quem conhece o processo.

## Uso do painel

1. Em **Nova análise**, adicione as fontes; a pilha é incremental. Para alternar entre computador e Drive, confirme a troca da seleção.
2. Escolha o tipo de documentação, informe o assunto, o público e os entregáveis. No perfil Processo / RPA, preencha também cliente, soluções e etapa. O guia de análise e cortes é gerado pelos campos; você pode acrescentar instruções, editar manualmente ou melhorar com IA. No modo local, o rascunho textual fica neste navegador; arquivos e autorização não são restaurados após fechar a página. Nas sessões autenticadas, o rascunho permanece apenas na sessão.
3. Revise e autorize o uso da API. Aguarde o upload terminar antes de fechar a página.
4. Em **Minhas análises**, busque e filtre os pedidos. Cancelar preserva as fontes; retomar reaproveita os arquivos recebidos. O cancelamento de uma etapa longa aguarda um ponto seguro.
5. A limpeza pede confirmação e remove somente trabalhos com falha ou cancelados e seus arquivos locais. Não é uma ação reversível pelo aplicativo.

## QA e ambiente isolado

O plano está em [docs/QA-IMPROVE-PLAN.md](docs/QA-IMPROVE-PLAN.md) e o aceite em [docs/QA-REPORT.md](docs/QA-REPORT.md). As verificações de backend e entregáveis têm relatórios próprios em `docs/`.

A nova etapa estruturada, a migração dos rascunhos e os limites de dados sensíveis estão documentados em [docs/CONTEXT-STEP.md](docs/CONTEXT-STEP.md).

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\qa_server.py
```

O servidor de QA usa dados e vídeos sintéticos em uma pasta exclusiva dentro de `cache/`, porta 8772, sem worker de processamento e sem credenciais de IA/Drive. Ele imprime o caminho `QA_FIXTURES` para o teste de upload. Com Playwright e Chrome disponíveis:

```powershell
node scripts\qa_browser.cjs --fixtures "<QA_FIXTURES>"
```

Se Playwright não estiver nas dependências locais, configure `NODE_PATH` para uma instalação existente. Evidências e capturas ficam em `cache/ui-qa-evidence/`, ignoradas pelo Git. `RPA_DATA_ROOT` permite isolar SQLite, arquivos e cache; credenciais continuam vindo do `.env` da aplicação.

Para mudanças de contexto, usar os testes correspondentes ao escopo, com o servidor sintético em 8772 e o preview exportado em 8773 quando necessário:

```powershell
node --test tests/test_context_model.cjs
node scripts\qa_structured_context.cjs
node scripts\qa_context_reconstruction.cjs
```

Para leitor, perfis e privacidade, os cenários estão em `scripts/qa_documentation_reader.cjs`, `scripts/qa_profiles.cjs`, `scripts/qa_context_privacy.cjs` e `scripts/qa_auth.cjs`. Consultar os relatórios antes de executar: cada suíte tem seu ambiente/fixtures. Login simulado valida apenas a interface e as regras exercitadas, não uma conta real no provedor.

## Antes de disponibilizar para a equipe

Esta é uma aplicação **local**. Exposição em rede requer autenticação, autorização e armazenamento isolado por usuário, gestão segura de tokens e credenciais, limites de consumo e uploads, política de retenção e operação do worker. A configuração OAuth real e a qualidade semântica precisam de aceite com uma reunião representativa. Não publique o servidor de desenvolvimento diretamente na internet.

## Google Drive

Crie um cliente OAuth do tipo aplicativo Web no Google Cloud, habilite a Drive API e configure no `.env`:

```text
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:8770/api/drive/callback
GOOGLE_DRIVE_FOLDER_ID=
```

Para importar fontes diretamente, o aplicativo solicita leitura do Drive; para publicar entregas, solicita gravação dos arquivos que ele cria. Ele nunca altera ou exclui as fontes. No protótipo local, a conexão representa um usuário. Quando a ferramenta ganhar autenticação de equipe, os tokens devem ser vinculados e criptografados por usuário no backend corporativo.

### Documentação estática com prints — 19/10/2026

PDF, Word e relatório HTML incorporam as evidências junto das etapas/itens, com legenda, arquivo de origem e horário. O HTML usa imagens incorporadas, sem depender de rede para mostrar os prints. Uma referência ausente ou imagem corrompida gera um aviso explícito, não uma imagem substituta. Evidências repetidas são referenciadas no PDF/Word sem duplicar a mesma figura.

Na etapa Contexto, **Formato de entrega** permite escolher:

- **Documentação com prints**: padrão dos novos pedidos; não renderiza previews. O resultado abre na aba Documentação. A revisão reaproveita transcrição e prints mesmo se o vídeo original não estiver disponível.
- **Documentação e vídeos com cortes**: mantém os previews individuais por gravação. Pedidos e rascunhos antigos sem essa escolha preservam este comportamento.

A API persiste essa escolha em `contexto.modoEntrega`: `documentacao` ou `documentacao_previews`. Abrir um trabalho antigo não o reprocessa automaticamente. Para atualizar sua documentação, solicite uma revisão; ela reutiliza a transcrição, pode consumir IA e permite cancelamento.

O arquivo **Dados e prints para integração** (`intercambio-documentacao.zip`) reúne `manifesto-documentacao.json` e apenas as imagens referenciadas, com identificadores, origem, horário, dimensões e SHA-256. É um contrato de intercâmbio versionado, ainda **não uma conexão com o motor As Is**. Template e API da ferramenta interna precisam de alinhamento.

### Arquivamento e recuperação no Drive

Além de **Enviar pacote ao Drive**, a aba Documentação oferece **Arquivar análise no Drive** quando há uma conta local conectada. Exige uma pasta de projeto configurada em Integrações. Envia fontes disponíveis, prints e entregas em uma estrutura por análise e revisão, com índice dos IDs remotos e hashes. Reenvios da mesma revisão reutilizam os arquivos; uma entrega alterada gera outra revisão. O índice só é confirmado no banco após o envio completo, e fontes ausentes são sinalizadas. Não altera permissões nem remove versões remotas.

**Recuperar arquivos do Drive** busca os arquivos da última revisão arquivada, inclusive em uma pasta local vazia. Confere metadados, tamanho e SHA-256 antes de publicar os arquivos recuperados. Não sobrescreve arquivos locais diferentes; uma revisão arquivada pode ser anterior à entrega atual. Não é um mecanismo de restauração do banco: o índice remoto fica associado ao trabalho no SQLite, cujo backup continua necessário.

Os endpoints são `POST /api/jobs/{id}/drive` com `include_assets: true` e `POST /api/jobs/{id}/drive/restore`. As ações exigem propriedade do trabalho e preservam o bloqueio do Drive por usuário autenticado enquanto os tokens corporativos individuais não forem implementados. Nada é enviado automaticamente. A integração foi testada com serviço simulado; OAuth, pasta e permissões corporativas ainda exigem aceite real.

O relatório da rodada, evidências, limitações e **Product QA Guardrails** estão em [docs/QA-STATIC-EVIDENCE-2026-10-19.md](docs/QA-STATIC-EVIDENCE-2026-10-19.md). Não há garantia de capturar cada mudança rápida de tela: a seleção visual ainda usa amostragem periódica e precisa de revisão humana.
