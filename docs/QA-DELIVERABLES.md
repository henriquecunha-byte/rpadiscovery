# QA dos entregáveis estruturados

Data: 08/10/2026. Escopo: exportação e revisão local, usando apenas dados e mídia sintéticos. Nenhuma gravação de cliente foi enviada a uma API; não houve chamada paga de IA.

## Resultado

Os entregáveis são documentos de processo, não apenas transcrição acompanhada de prints. Word e PDF contêm 13 seções principais: objetivo, escopo, atores, sistemas, pré-requisitos, entradas/saídas, fluxo operacional, regras, exceções, riscos/controles, oportunidades, pontos a validar e limitações. O HTML separa essa estrutura do anexo de evidências e dos previews por arquivo.

O conteúdo sintético deliberadamente deixa vários campos como não identificados. Isso valida o comportamento diante de informação ausente; não demonstra qualidade semântica da IA em uma reunião real.

## Achados e correções

| Achado reproduzido | Correção aplicada | Evidência |
|---|---|---|
| Fallback copiava o guia de corte como objetivo e resumo do processo. | Objetivo passa a ser explicitamente não confirmado; resumo identifica registro preliminar. Guia recebido é uma seção separada em Word, PDF, HTML e Markdown. | Teste de fallback; texto dos arquivos; capa PDF e relatório HTML inspecionados. |
| SOP e requisitos Markdown omitiam limitações de uma síntese incompleta. | Ambos incluem guia e limitações do mesmo documento estruturado. | Teste lê os dois arquivos exportados e encontra o aviso sintético integral. |
| Último bullet de limitação ficava sozinho na quarta página do PDF. | Lista curta mantida com o título; espaçamento vertical refinado sem reduzir o corpo de 10,5 pt. | PDF final tem 3 páginas; todas renderizadas e inspecionadas. |
| Exports mantinham navy/teal antigos. | Noite, violeta, lavanda e neutros Btime aplicados nos três formatos visuais. HTML incorpora as três WOFF oficiais, funcionando offline. | Screenshots e fontes carregadas no Chromium; render PDF. |
| Título Word era um parágrafo Normal e rodapé não trazia página. | Estilo Title, metadados de título/assunto/autor e campo PAGE no rodapé. | Inspeção python-docx/XML e teste automatizado. |
| Rodapé PDF imprimia o título inteiro sem limite de largura. | Título reduzido com reticências somente no rodapé, preservando capa/metadados. | Teste com título extenso confirma coordenada esquerda dentro da margem. |

## Provas executadas

- Suíte integrada no `.venv`: **67 testes, 67 aprovados, sem skips**. O leitor opcional `pypdf` já existente no runtime foi adicionado ao fim de `sys.path`; dependências do projeto continuaram prioritárias. Nenhum pacote foi instalado.
- Regressão de mídia/documentos no runtime empacotado: **18 testes aprovados**, incluindo 4 testes novos de entregáveis. OpenAI e carregamento de credenciais desativados explicitamente nessa rodada documental.
- Documento Word extraído: 13 headings principais e 4 tabelas; cabeçalhos de tabela repetíveis. Título semântico, campos de página e avisos verificados no XML.
- PDF final: 3 páginas Letter; texto extraído com pypdf; cada página renderizada pelo Poppler e inspecionada visualmente. Sem texto cortado, colisão com rodapé ou limitação órfã na amostra.
- HTML em Chromium headless, aberto como arquivo local, em **1440 × 1000** e **375 × 1000**: nenhuma rolagem horizontal da página, nenhum arquivo local referenciado ausente e nenhum erro de JavaScript.
- Sem solicitações HTTP externas. As três fontes Branding foram carregadas a partir dos dados incorporados ao HTML. Foco de teclado no primeiro download: contorno sólido visível de 3 px.
- Os dois previews e o player de evidência tocaram nos dois tamanhos de viewport: `readyState=4`, avanço real do tempo e nenhum erro de mídia. Cada preview tem aproximadamente 12,02 s na amostra.
- ZIP final: 17 entradas; teste de integridade CRC sem erro. Inclui documentos, dados estruturados, transcrição, matriz, evidências, roteiros e dois previews separados.
- `git diff --check` sem erros de whitespace; Git apenas avisou sobre conversão futura LF/CRLF em arquivos do checkout.

## Artefatos locais de evidência

A fixture original do servidor foi preservada em `cache/ui-qa-9lwa47p1/jobs/qa-completed`. A versão refinada foi gerada separadamente:

- Documentos e ZIP: `cache/ui-qa-9lwa47p1/deliverable-qa/refined/`.
- PDF renderizado: `cache/ui-qa-9lwa47p1/deliverable-qa/final-page-1.png` até `final-page-3.png`.
- Screenshots HTML desktop/mobile e evidência em vídeo: `cache/ui-qa-9lwa47p1/deliverable-qa/browser/`.
- Resultados detalhados do navegador: `cache/ui-qa-9lwa47p1/deliverable-qa/browser/results.json`.
- Harness reproduzível: `tests/qa_deliverables_browser.cjs`.
- Testes de exportação: `tests/test_deliverables_qa.py`.

Hashes SHA-256 desta execução:

```text
documentacao-processo.pdf
8D9821AD977A975C6779F5F443AAE310D17C07E58DC213225D5A293FCDEAEBB5

entrega-completa.zip
47F2BAB1F4A0547EBE32D367A7B7404EF60735E3CAC2D4E6382B67C7393DB85A
```

## Limites e pendências antes de produção

1. **Sem validação semântica real nesta rodada.** Acerto de nomes, regras, contexto e cortes requer uma reunião representativa e revisão do responsável. Os testes não afirmam que a IA compreendeu o processo real.
2. **Word não foi renderizado visualmente.** O runtime documental não inclui LibreOffice. Word desktop 16.0.20430.20092 e o registro COM foram confirmados por leitura local. Uma tentativa suplementar de automação foi interrompida antes de abrir o DOCX porque a guarda não conseguiu obter HWND/confirmar o PID da nova instância. Não houve exportação PDF pelo Word nem encerramento forçado de processos; referências COM foram liberadas. A prova Word permanece estrutural/XML, não uma promessa sobre paginação em todos os clientes.
3. **Tipografia portável explícita.** Word usa Arial e PDF usa Helvetica para compatibilidade, com nota nos documentos. As WOFF oficiais foram incorporadas apenas ao HTML; não foram convertidas nem embutidas no Word/PDF. Cores oficiais estão aplicadas em todos.
4. **PDF não é tagged/PDF-UA.** Há texto selecionável e hierarquia visual, mas acessibilidade completa por leitor de tela no PDF ainda não foi certificada. HTML e Word preservam headings semânticos.
5. **Amostra pequena.** Layouts com tabelas muito extensas, texto excepcionalmente longo ou centenas de etapas não foram aprovados visualmente nesta rodada. O renderer permite quebra das listas longas, mas isso não substitui a revisão de amostras extensas.
6. **Não é uma atualização retroativa dos jobs.** Arquivos antigos permanecem como estavam. A nova exportação será produzida em novas análises/reconstruções; a fixture original também foi mantida intacta durante o QA.

O Poppler emitiu avisos de fontes de substituição Symbol/ArialUnicode. Os glifos e marcadores efetivamente usados na amostra foram conferidos visualmente e aparecem corretamente; os avisos não foram tratados como prova de falha do arquivo.
