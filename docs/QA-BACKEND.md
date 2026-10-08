# QA do backend — 8 de outubro de 2026

Verificação realizada em banco e diretórios temporários, com `RPA_DATA_ROOT` isolado. Nenhuma gravação existente foi processada; Google Drive e síntese foram simulados nos testes que exercitam integrações externas.

## Resultado

- Suíte integrada final: **67 testes**, 66 aprovados e 1 leitura PDF opcional ignorada na `.venv` isolada, em 8,261 segundos (`python -m unittest discover -s tests -v`). A verificação do agente de entregáveis, com o leitor PDF disponível no runtime, confirmou **67/67 aprovados**, sem testes ignorados, em 8,67 segundos.
- `git diff --check`: aprovado; somente avisos de conversão LF/CRLF do Git.
- Novas regressões do backend: 17 de API, 12 de fila/revisão e 6 do Google Drive.
- Os testes integrados incluem mídia sintética e validações de documentação mantidas pela suíte do pipeline.

## Correções verificadas

- Multipart valida título, nível, contexto, orçamento e consentimento antes de criar o diretório do trabalho. Arquivos vazios e ZIPs inválidos retornam erro legível; falhas removem os arquivos temporários daquele envio.
- Caminhos de upload rejeitam escape de diretório, caminhos absolutos e nomes especiais do Windows. Arquivos duplicados no envio, ZIP ou Drive são preservados com nomes distintos.
- Leitura do histórico e do detalhe normaliza `result_json`, incluindo registros legados inválidos.
- A fila reserva um trabalho atomicamente. Cancelamento não é sobrescrito por atualização tardia de progresso ou conclusão; retomar respeita a ordem de chegada e reinicia a estimativa.
- Reinício recupera trabalhos interrompidos e conclui cancelamentos pendentes. Abrir outro leitor do banco não reinicia trabalhos ativos.
- Limpeza da fila protege trabalhos que já foram retomados e preserva seus eventos.
- Revisão de documentos retorna HTTP 202 e acompanha a mesma fila (`operation=rebuild`). Usa a transcrição já existente, admite cancelamento/retomada e publica os novos artefatos depois de gerar a revisão. Falha ou cancelamento durante geração conserva a entrega anterior.
- Preview aceita requisições HTTP Range (206) para reprodução e busca no navegador; cada documento tem um link próprio. Artefatos antigos/parciais ficam ocultos durante processamento.
- Google Drive pagina a listagem, escapa consultas, suporta parâmetros de drives compartilhados e remove downloads parciais. O retorno da listagem permanece um array compatível com a interface.

## Contratos adicionados

- `RPA_DATA_ROOT`: raiz opcional de dados, jobs e cache; o `.env` continua sendo o do projeto.
- `GET /api/health`: `worker`, `ffmpeg`, `ffprobe`, `api_configured` booleanos, sem credenciais.
- Jobs: `operation`, `queued_at`, `result_json` sempre objeto, `documents` com `filename`, `label`, `format`, `available` e `url`.
- `POST /api/jobs/{id}/rebuild-documents`: HTTP 202, trabalho enfileirado; endpoints de cancelar e retomar continuam os mesmos.
- Disponibilidade por trabalho: `delivery_missing` e motivo, `source_available`, `can_retry`, `can_rebuild` e motivos de indisponibilidade. Revisar e retomar retornam HTTP 409 acionável quando faltam arquivos; a interface orienta restaurar a pasta original ou reutilizar o pedido com um novo envio.

## Limites da verificação

OAuth/Drive reais, chamadas pagas de análise e qualidade semântica de uma reunião real não foram executados neste QA. O cancelamento interrompe entre etapas seguras; uma chamada externa ou renderização já iniciada pode precisar terminar antes de o status mudar para cancelado. O aplicativo continua um serviço local com um worker; acesso público por equipes exige a arquitetura de autenticação e hospedagem correspondente.

## Verificação dos registros reais preexistentes

O banco real foi consultado usando SQLite `mode=ro`, somente para contar status e verificar existência dos caminhos, sem ler conteúdo das gravações e sem executar análises. Há **4 trabalhos: 3 concluídos e 1 com falha**.

As quatro pastas de trabalho e as fontes registradas estão ausentes do checkout atual. Nenhum dos oito entregáveis padrão verificados está disponível para cada trabalho; os três previews declarados em dois resultados também estão ausentes. O diretório legado originalmente registrado no projeto local do Codex não existe mais. As alternativas específicas em `C:\Dev\btime-tools` e na pasta Btime do OneDrive também não foram encontradas.

Portanto, os registros do histórico foram preservados, mas as entregas antigas não acompanham esta cópia do projeto. Isso já existia antes do refinamento. Os arquivos não foram removidos, copiados ou reprocessados neste QA; para recuperar essas entregas será necessário localizar uma cópia das pastas originais ou reenviar as gravações.

A interface agora distingue essa ausência de arquivos de uma análise sem trechos contextuais. O histórico continua visível; revisão sem insumos fica oculta e retomada sem fonte fica desabilitada com explicação, mantendo disponível a reutilização dos campos do pedido. A compatibilidade de caminhos legados é aplicada somente quando uma retomada é solicitada e a gravação realmente existe no diretório atual.
