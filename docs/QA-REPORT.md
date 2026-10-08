# btime Discovery — relatório de refinamento

Data: 08/10/2026. Estado: **versão candidata local**, com interface, fila, processamento e entregáveis revisados. Não é uma publicação corporativa nem uma certificação de acerto semântico da IA.

## Planejamento e escopo

O plano foi registrado antes da implementação em [QA-IMPROVE-PLAN.md](QA-IMPROVE-PLAN.md). Foram executadas as oito frentes: diagnóstico, arquitetura de navegação, entrada de gravações, acompanhamento, entrega, confiabilidade, identidade/acessibilidade e aceite.

O trabalho preservou a arquitetura FastAPI/SQLite/HTML/CSS/JavaScript, o histórico existente e os arquivos originais de marca. Não foram criados commits, feitos pushes, alterados remotes ou publicados serviços externos.

## O que mudou para quem usa

- **Nova análise em três etapas:** gravações, contexto e revisão. Arquivos, pastas e ZIPs entram numa pilha incremental, com deduplicação e remoção individual. Trocar entre computador e Drive exige confirmação.
- **Pedido claro e recuperável:** rascunho textual local, validações por campo, sugestão de guia sem sobrescrever edições silenciosamente, autorização explícita e revisão antes de iniciar.
- **Envio confiável:** progresso do upload, bloqueio de clique duplicado e preservação de campos/fontes em caso de falha.
- **Histórico utilizável:** busca, filtros, indicadores de entregas realmente disponíveis, cancelamento, retomada e limpeza confirmada de falhas/cancelados.
- **Acompanhamento:** etapa, tempo decorrido, estimativa e pedido original; atualização não reinicia o player nem troca a tela em uso. Dados de tempo ausentes não são apresentados como duração zero.
- **Entrega organizada:** previews separados por gravação, roteiro clicável de cortes, downloads individuais, Word, PDF, procedimento, requisitos, matriz de evidências, dados estruturados e ZIP.
- **Erros acionáveis:** um histórico sem os arquivos da migração é distinguido de um vídeo sem conteúdo relevante. O pedido pode ser reutilizado; operações sem insumos são bloqueadas com explicação.
- **Marca oficial:** identidade Btime, fontes locais, SVGs e imagem fornecidos, foco visível, dialogs nativos, responsividade e movimento reduzido. Detalhes em [BRAND-IMPLEMENTATION.md](BRAND-IMPLEMENTATION.md).

## Correções técnicas relevantes

Uploads validam campos antes de criar trabalho e rejeitam ZIP inválido, escape de diretório e arquivos vazios. Nomes duplicados não sobrescrevem gravações.

A fila reserva trabalho atomicamente, protege cancelamento contra respostas tardias e recupera interrupções. Revisar documentos usa a fila normal, com HTTP 202 e publicação dos artefatos após a geração.

Gravações com dimensões, taxas de quadros e áudio diferentes são normalizadas para análise. Previews usam formato compatível com navegador, coordenadas de cortes válidas e intervalos por fonte. Uma seleção contextual vazia não vira automaticamente um corte por prints. O ZIP segue o manifesto atual, sem carregar previews obsoletos.

Os documentos separam contexto recebido de fatos confirmados, preservam limitações em cada formato e usam uma estrutura operacional. Há provas detalhadas em [QA-BACKEND.md](QA-BACKEND.md) e [QA-DELIVERABLES.md](QA-DELIVERABLES.md).

## Evidências de aceite

- **67/67 testes Python aprovados**, incluindo API, fila, Drive simulado, vídeo real sintético e exportações. Para a verificação PDF, foi utilizado o leitor pypdf já presente no runtime, sem instalar pacotes.
- **35/35 cenários principais no Chrome**: formulário, upload real sintético, prevenção de duplicidade, histórico, filtros, reprodução de ambos os previews, HTTP Range 206, downloads, teclado, cancelamento/retomada, segurança de texto dinâmico e responsividade.
- **12/12 cenários adicionais**: pasta com subpastas e leitura em lotes, deduplicação, nomes longos, navegação/seleção do Drive simulado, troca de origem confirmada, falha de importação, sugestão tardia, formulário móvel, animação habilitada, navegação pelos cortes e erro 404.
- **Quatro larguras conferidas**: 375, 768, 1024 e 1440 px, sem overflow horizontal de página nas telas testadas.
- **Histórico real conferido somente leitura**: quatro registros, sem requisições mutantes; três entregas ausentes corretamente sinalizadas e uma retomada sem fonte bloqueada. API, worker e ferramentas de vídeo disponíveis no ambiente local.
- **HTML exportado offline** em desktop/celular: fontes locais carregadas, nenhum link de arquivo ausente, nenhuma chamada externa, foco de teclado e reprodução de previews/evidência.
- **PDF inspecionado visualmente**, página por página; amostra final em três páginas, sem clipping ou bullet órfão. ZIP com integridade CRC e manifestos verificados.
- Sintaxe JavaScript e git diff --check aprovados. Sem erros de JavaScript não tratados nos cenários de navegador.

As provas usam mídia sintética e integrações externas simuladas. Não demonstram precisão da IA em uma reunião real nem redução medida dos aproximadamente dez minutos relatados no uso anterior.

## Como abrir e reproduzir

Aplicativo: http://127.0.0.1:8770. Inicialização habitual pelo start.ps1 na raiz do projeto.

Roteiros reproduzíveis:

- scripts/qa_server.py: servidor isolado, vídeos sintéticos e nenhuma execução de worker/IA; imprime QA_FIXTURES.
- scripts/qa_browser.cjs --fixtures CAMINHO: cenários principais.
- scripts/qa_browser_edges.cjs CAMINHO: cenários adicionais, incluindo Drive simulado.
- scripts/qa_existing_readonly.cjs: inspeção somente leitura do ambiente real.
- tests/qa_deliverables_browser.cjs: relatório offline.

Playwright deve estar disponível no Node; nesta máquina foi usado o runtime já instalado. Evidências e resultados ficam em cache/ui-qa-evidence, fora do Git. A fixture final desta rodada está em cache/ui-qa-x1bs48r8; a revisão visual específica dos documentos está em cache/ui-qa-9lwa47p1/deliverable-qa.

## Pendências honestas

1. **Arquivos antigos:** os quatro registros do histórico vieram sem suas pastas de fontes/entregáveis. Elas já estavam ausentes; nada foi removido neste QA. Para recuperar entregas antigas, localizar uma cópia das pastas originais ou reenviar as gravações reutilizando o pedido.
2. **Aceite semântico e desempenho:** testar uma reunião representativa com o guia desejado, revisar nomes, assunto, regras, exceções e cortes, e medir o tempo completo. Não houve chamada paga de IA nesta rodada.
3. **Drive real:** cliente OAuth não configurado neste ambiente. Fluxo e tratamento de erros foram testados com respostas controladas; a autorização da conta Google depende da configuração real.
4. **Uso corporativo:** autenticação, autorização e isolamento por integrante, hospedagem/worker, política de retenção, limites de upload e gestão de credenciais precisam ser definidos antes de disponibilizar em rede. O orçamento informado é referência, não teto automático de cobrança.
5. **Validação dos exports:** Word validado estruturalmente, sem prova visual de paginação no Office. PDF não é tagged/PDF-UA; revisão visual e estrutural não equivalem a certificação com leitores de tela. Limites de compatibilidade e amostras estão no relatório de entregáveis.
6. **Publicação Git/Lovable:** pendente do repositório correto vinculado ao projeto do Lovable. O remote atual foi preservado.

Nenhum servidor foi exposto além de 127.0.0.1.
