# Btime RPA Docs

Aplicativo local para transformar gravações de discovery em documentação operacional de RPA, cruzando transcrição, prints e análise visual.

## Entrega da primeira versão

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
- orçamento informado e autorização explícita por execução;
- isolamento completo entre gravações em `jobs/<id>`.
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

O botão **Gerar prompt automaticamente**, ao lado do contexto, monta o texto que orienta a análise: ele parte do nome do processo, do público, do nível de detalhe, do rascunho já digitado e dos arquivos na pilha. A primeira linha declara o assunto do discovery, porque é ela que decide o que permanece no preview — cada bloco falado é mantido ou descartado conforme pertencer a esse assunto.

Sem `OPENAI_API_KEY` configurada, o botão devolve um prompt base montado localmente com as mesmas regras e avisa que a API não respondeu. O texto sempre pode ser editado antes de criar a documentação.

## Downloads da entrega

Com o trabalho concluído, o painel de acompanhamento oferece o pacote ZIP completo, a **gravação analisada** (a consolidada quando há vários arquivos na pilha) e a **documentação em PDF**. O PDF acompanha as mesmas seções do documento Word e é gerado sob demanda para trabalhos concluídos antes desta versão.

## Google Drive

Crie um cliente OAuth do tipo aplicativo Web no Google Cloud, habilite a Drive API e configure no `.env`:

```text
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:8770/api/drive/callback
GOOGLE_DRIVE_FOLDER_ID=
```

Para importar fontes diretamente, o aplicativo solicita leitura do Drive; para publicar entregas, solicita gravação dos arquivos que ele cria. Ele nunca altera ou exclui as fontes. No protótipo local, a conexão representa um usuário. Quando a ferramenta ganhar autenticação de equipe, os tokens devem ser vinculados e criptografados por usuário no backend corporativo.
