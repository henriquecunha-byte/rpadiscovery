# Btime Discovery

Aplicativo local para transformar gravações em documentos para diferentes áreas, cruzando transcrição, evidências visuais e o contexto de cada pedido. O pacote Python e os caminhos históricos mantêm o nome `rpa_docs` por compatibilidade.

O provedor padrão de IA é agora o **Lovable**. Este repositório ainda executa o worker Python, SQLite e arquivos locais; configurar o gateway não migra dados nem publica esse worker no Lovable Cloud. A separação entre as duas partes está em [Integração com Lovable](docs/LOVABLE-INTEGRATION.md).

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

## Login e acesso da equipe

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
