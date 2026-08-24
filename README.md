# Btime RPA Docs

Aplicativo local para transformar gravações de discovery em documentação operacional de RPA, cruzando transcrição, prints e análise visual.

## Entrega da primeira versão

- fila local de trabalhos e histórico em SQLite;
- upload por arrastar e soltar de um vídeo ou uma pasta inteira;
- consolidação automática de várias gravações, sem depender de editor externo;
- captura de evidências visuais com timecode;
- transcrição local com Faster-Whisper;
- descrição visual baseada somente em evidências observáveis;
- preview MP4 com os trechos relevantes e cortes conservadores;
- relatório HTML navegável e JSON estruturado por trabalho;
- pacote ZIP com relatório, preview, prints, transcrição e dados estruturados;
- conexão opcional com Google Drive por OAuth e envio do pacote para uma pasta compartilhada;
- orçamento informado e autorização explícita por execução;
- isolamento completo entre gravações em `jobs/<id>`.
- cancelamento de trabalhos na fila ou em processamento, preservando os arquivos já recebidos;
- retomada de trabalhos com falha ou cancelados sem repetir o upload;
- acompanhamento com tempo decorrido, etapa, posição na fila e previsão restante baseada no ritmo atual e no histórico;
- resumo permanente do guia, público e nível de detalhe de cada pedido;

## Princípios

- A gravação original nunca é alterada.
- Cada descrição aponta para um print e um momento da gravação.
- A análise deve declarar incerteza e não inferir cliques ou valores invisíveis.
- A chave fica apenas no arquivo local `.env`, ignorado pelo Git.
- O JSON intermediário permite exportação futura para Word, PDF ou template Btime.

## Execução

```powershell
.\setup.ps1
.\start.ps1
```

O painel abre em `http://127.0.0.1:8770`.

## Google Drive

Crie um cliente OAuth do tipo aplicativo Web no Google Cloud, habilite a Drive API e configure no `.env`:

```text
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:8770/api/drive/callback
GOOGLE_DRIVE_FOLDER_ID=
```

Para importar fontes diretamente, o aplicativo solicita leitura do Drive; para publicar entregas, solicita gravação dos arquivos que ele cria. Ele nunca altera ou exclui as fontes. No protótipo local, a conexão representa um usuário. Quando a ferramenta ganhar autenticação de equipe, os tokens devem ser vinculados e criptografados por usuário no backend corporativo.
