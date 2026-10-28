# Etapa Contexto estruturada

Implementação local de 08/10/2026, baseada no `spec-etapa-contexto.md` fornecido pelo usuário. Mantém FastAPI, SQLite e JavaScript/CSS nativos, sem bibliotecas novas, publicação, commit, push ou conexão ao Supabase.

## Plano executado

1. Modelar o contexto e as regras compartilhadas; migrar rascunhos antigos sem apagar o guia manual.
2. Substituir o campo livre principal pelos blocos Projeto, Destino, Entregáveis, Ambiente e Guia; integrar revisão e envio.
3. Validar contratos, erros seguros, teclado, telas menores, privacidade e uma entrega com duas gravações sintéticas.

## Comportamento

- Cliente, processo, objetivo, soluções, etapa de destino e público determinam o guia. Nenhum nome de cliente é preenchido automaticamente.
- RPA como única solução sugere Especificação de RPA enquanto a pessoa não tiver escolhido uma etapa. A matriz de entregáveis aplica a união das sugestões por etapa e solução, até a seleção ser personalizada.
- Sistemas são tags com limite de 15. O guia é determinístico, atualizado pelos campos e disponível sem IA. Nomes de arquivos não são acrescentados ao guia nem enviados como metadados à sugestão.
- Editar manualmente ou aceitar uma melhoria da IA trava a atualização automática do guia. Voltar ao texto gerado exige confirmação; uma resposta tardia da IA também exige confirmação se o pedido mudou.
- Validação acontece ao sair do campo/grupo ou continuar. O botão Continuar permanece habilitado e direciona para o primeiro campo inválido. Campos de erro reservam espaço para evitar deslocamento durante cliques.
- A revisão mostra cliente, processo, soluções, etapa, público e entregáveis. O aviso de dados sensíveis não promete anonimização automática.

## Contratos e armazenamento

`context-rules.json` é a fonte única de labels, matriz, tom, foco e regras de corte/evidência. `context-model.js` e `context_model.py` compilam os mesmos snapshots.

O objeto `contexto` é validado no servidor para uploads, criação local e importação do Drive. Se `guiaEditado=false`, o servidor recompila o guia e ignora o texto automático enviado pelo navegador. Se `true`, preserva o guia manual não vazio, até 8.000 caracteres. A partir dele deriva os campos legados `title`, `process_context`, `audience` e `detail_level`, preservando o pipeline atual.

O SQLite ganha apenas a coluna nullable `contexto_json`. Registros antigos continuam válidos com `contexto=null`; registros novos guardam os campos junto da análise e mantêm o proprietário existente. A API expõe `contexto`, não a coluna serializada. O rascunho usa payload `{version:2, contexto, api_budget_usd}` na chave local original para migrar no lugar. Sessões autenticadas continuam sem rascunho em localStorage compartilhado.

O endpoint de melhoria usa `{ok:true,prompt}` ou `{ok:false,code:"ai_unavailable"}`. Falhas do provedor não se transformam em HTTP 401 de autenticação do aplicativo. A interface mantém o guia atual e mostra aviso neutro. Logs novos contêm somente operação permitida, classe da exceção e status inteiro; sem body, mensagem ou traceback do SDK. Erros novos do worker e das exportações também usam mensagens fixas. Registros e arquivos históricos não são reescritos por esta mudança.

## Limites deliberados

- **Dados sensíveis:** o flag acrescenta instruções ao guia; não mascara automaticamente áudio, vídeo, prints ou a transcrição original. Revisão antes de compartilhar continua obrigatória. O mascaramento de regiões fica como implementação futura, não como capacidade entregue.
- A seleção de entregáveis orienta o conteúdo da análise; não muda o conjunto de formatos que o pipeline gera.
- A análise semântica usa o pipeline existente, sem mudanças nos algoritmos de corte ou transcrição. Testes com inferência simulada não validam a precisão de uma reunião real.
- A chave real não foi exibida nem utilizada em chamadas pagas durante este QA. Autenticação corporativa e Drive por conta permanecem no escopo futuro já documentado.

## Validação reproduzível

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests
node --test tests\test_context_model.cjs
.\.venv\Scripts\python.exe -X utf8 scripts\qa_server.py
node scripts\qa_structured_context.cjs
node scripts\qa_browser.cjs --fixtures "<QA_FIXTURES>"
node scripts\qa_browser_edges.cjs
node scripts\qa_context_privacy.cjs
node scripts\qa_auth.cjs
.\.venv\Scripts\python.exe -X utf8 scripts\qa_context_pipeline.py --fixtures "<QA_FIXTURES>"
node scripts\qa_existing_readonly.cjs
```

Playwright/Chrome devem estar disponíveis; pode-se apontar NODE_PATH para o runtime existente. O teste de PDF da suíte completa requer pypdf. O ambiente desta entrega usou o pypdf do runtime já instalado, sem instalar pacotes no projeto.

Resultados verificados: 176 testes Python, 18 testes Node e 93 cenários de navegador passaram (25 do novo contexto, 35 principais, 12 de borda, 16 de autenticação simulada e 5 de privacidade). A integração sintética executou FFmpeg, dois previews separados, documentos Word/PDF e integridade CRC do ZIP; apenas transcrição e inferência foram simuladas. Os relatórios de navegador ficam em `cache/context-qa-evidence`, `cache/ui-qa-evidence`, `cache/auth-qa-evidence` e `cache/context-privacy-qa-evidence`. A etapa e o guia foram inspecionados visualmente em 1440 e 375 px; o ajuste de acessibilidade mantém o link de pular conteúdo oculto até receber foco, inclusive com movimento reduzido.

O servidor principal foi reiniciado somente após confirmar a fila ociosa e criar `cache/before-structured-context-20261008-093159.sqlite3`. A conferência posterior, somente leitura, preservou os quatro registros existentes (três concluídos e um com falha), sem reprocessamento. As três entregas ausentes desde a migração continuam sinalizadas; nenhum arquivo histórico foi apagado.
