# Btime RPA Docs

Aplicativo local para transformar gravações de discovery em documentação operacional de RPA, cruzando transcrição, prints e análise visual.

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
- documentação orientada ao processo, com objetivo, escopo, atores, sistemas, pré-requisitos, entradas, saídas, regras, exceções, riscos e oportunidades de automação;
- documento Word editável, documento PDF, procedimento operacional, requisitos para RPA e matriz de evidências separados da transcrição bruta;
- download da gravação analisada e exportação da documentação em PDF direto do painel de acompanhamento;
- pacote ZIP com relatório, preview, prints, transcrição, PDF e dados estruturados;
- conexão opcional com Google Drive por OAuth e envio do pacote para uma pasta compartilhada;
- orçamento de referência (não é um teto automático de cobrança) e autorização explícita por execução;
- diretório separado para cada análise em `jobs/<id>`; o ambiente local ainda não possui autenticação e isolamento por integrante da equipe;
- cancelamento de trabalhos na fila ou em processamento, preservando os arquivos já recebidos;
- retomada de trabalhos com falha ou cancelados sem repetir o upload;
- acompanhamento com tempo decorrido, etapa, posição na fila e previsão restante baseada no ritmo atual e no histórico;
- resumo permanente do guia, público e nível de detalhe de cada pedido;
- limpeza em lote de trabalhos cancelados ou com falha, incluindo seus arquivos locais, mediante confirmação;

## Princípios

- A gravação original nunca é alterada.
- Cada descrição aponta para um print e um momento da gravação.
- A análise deve declarar incerteza e não inferir cliques ou valores invisíveis.
- A chave fica apenas no arquivo local `.env`, ignorado pelo Git.
- O JSON intermediário sustenta as exportações em Word, PDF e template Btime.

## Execução

```powershell
.\setup.ps1
.\start.ps1
```

O painel abre em `http://127.0.0.1:8770`.

## Prompt automático do discovery

O botão **Ajudar a escrever**, na etapa Contexto, sugere o texto que orienta a análise: ele parte do nome do processo, do público, do nível de detalhe, do rascunho já digitado e dos arquivos na pilha. O guia declara o assunto do discovery e orienta quais blocos falados permanecem no preview. Revise a sugestão antes de autorizar a execução.

Sem `OPENAI_API_KEY` configurada, o botão devolve um prompt base montado localmente com as mesmas regras e avisa que a API não respondeu. O texto sempre pode ser editado antes de criar a documentação.

## Downloads da entrega

Com o trabalho concluído, **Vídeos e cortes** oferece um player e um download por gravação, com o roteiro dos trechos mantidos. A aba **Documentação** reúne relatório navegável, Word, PDF, procedimento, requisitos, matriz de evidências e dados estruturados. **Baixar pacote completo** reúne os materiais no ZIP. O PDF acompanha as mesmas seções do Word e é gerado sob demanda para trabalhos antigos.

Quando a transcrição ou a síntese estiver indisponível, a entrega declara a limitação. Não são criados cortes supostamente contextuais apenas a partir de prints. Documentos e inferências precisam da revisão de quem conhece o processo.

## Uso do painel

1. Em **Nova análise**, adicione as fontes; a pilha é incremental. Para alternar entre computador e Drive, confirme a troca da seleção.
2. Informe o processo e o guia de análise e cortes. O rascunho textual fica neste navegador; arquivos e autorização não são restaurados após fechar a página.
3. Revise e autorize o uso da API. Aguarde o upload terminar antes de fechar a página.
4. Em **Minhas análises**, busque e filtre os pedidos. Cancelar preserva as fontes; retomar reaproveita os arquivos recebidos. O cancelamento de uma etapa longa aguarda um ponto seguro.
5. A limpeza pede confirmação e remove somente trabalhos com falha ou cancelados e seus arquivos locais. Não é uma ação reversível pelo aplicativo.

## QA e ambiente isolado

O plano está em [docs/QA-IMPROVE-PLAN.md](docs/QA-IMPROVE-PLAN.md) e o aceite em [docs/QA-REPORT.md](docs/QA-REPORT.md). As verificações de backend e entregáveis têm relatórios próprios em `docs/`.

```powershell
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
