# Documentação por perfil — implementação e QA

Data: 14/10/2026. Escopo: adequar o Discovery a diferentes áreas sem perder o fluxo de Processo / RPA ou alterar análises existentes.

## Plano executado

1. Compartilhar seis perfis entre formulário e backend; novos pedidos em Personalizado, pedidos antigos sem perfil em Processo / RPA.
2. Tornar contexto e entregáveis condicionais: assunto obrigatório, área opcional e públicos gerais; solução e etapa técnica restritas ao perfil de processo.
3. Separar o contrato de síntese geral do contrato operacional, usando somente as seções solicitadas e marcando lacunas sem inventar fatos.
4. Alimentar Word, PDF, HTML, Markdown e JSON pela mesma estrutura. Manter preview individual por gravação, matriz de evidências e ZIP completo.
5. Validar compiladores, API, autorização, rascunhos, geração real de mídia, exportações e interface com dados sintéticos, sem consumo externo de IA.

## Comportamento por perfil

| Perfil | Organização sugerida | Markdown |
| --- | --- | --- |
| Personalizado | Temas, decisões e próximos passos; guia livre | `documentacao.md` |
| Reunião | Temas, decisões e encaminhamentos | `registro-reuniao.md` |
| Treinamento | Conceitos, exemplos, aprendizados e perguntas | `guia-treinamento.md` |
| Entrevista | Perguntas, respostas, temas e achados | `registro-entrevista.md` |
| Pesquisa | Temas, achados, recomendações e hipóteses | `relatorio-pesquisa.md` |
| Processo / RPA | Fluxo, sistemas, regras, exceções e requisitos | `procedimento-operacional.md` e `requisitos-rpa.md` |

As sugestões podem ser ajustadas entre os entregáveis disponíveis em cada perfil. O perfil muda o contrato de documentação, não cria um agente autônomo adicional. Transcrição, análise visual e seleção de cortes continuam usando o pedido como referência, com prioridade ao conteúdo falado. Guias manuais não são sobrescritos ao trocar o perfil.

Nos perfis gerais, `documentacao.docx`, `documentacao.pdf` e `documentacao.json` substituem os nomes operacionais. O ZIP não inclui requisitos de RPA nem arquivos obsoletos de outro perfil. Os links de trabalhos antigos permanecem compatíveis. Não foi necessária migração destrutiva do SQLite.

## Verificações

| Camada | Resultado | Evidência reproduzível |
| --- | --- | --- |
| Python / API / segurança de acesso | 188 testes executados: 187 PASS, 1 SKIP | `.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -q` |
| Compilador JS e migração de rascunhos | 19 PASS | `node --test tests/test_context_model.cjs` |
| Navegador: fluxo principal | 35 PASS | `scripts/qa_browser.cjs` |
| Navegador: casos de erro e bordas | 12 PASS | `scripts/qa_browser_edges.cjs` |
| Navegador: contexto de processo | 25 PASS | `scripts/qa_structured_context.cjs` |
| Navegador: cinco perfis gerais | 17 PASS | `scripts/qa_profiles.cjs` |
| Navegador: acesso e login preparado | 16 PASS, provedor futuro simulado | `scripts/qa_auth.cjs` |
| Navegador: troca de conta e rascunhos | 5 PASS, contas simuladas | `scripts/qa_context_privacy.cjs` |
| Pipeline com FFmpeg e exportações reais | 6 PASS, dois vídeos por perfil | `scripts/qa_context_pipeline.py --fixtures <pasta-QA> --profile <perfil>` |

O único SKIP é o leitor opcional `pypdf` ausente. O PDF foi efetivamente gerado pelo ReportLab e a primeira página de uma reunião foi renderizada com Poppler e inspecionada visualmente. Word foi aberto pela biblioteca de DOCX e seu conteúdo conferido; não houve inspeção no Microsoft Word.

Evidências locais ignoradas pelo Git: `cache/profiles-qa-evidence/`, `cache/context-privacy-qa-evidence/`, `cache/auth-qa-evidence/` e `cache/ui-qa-evidence/`. Testes de navegador usam exclusivamente o servidor sintético em `127.0.0.1:8772`; a instância de uso normal é `127.0.0.1:8770`.

### Instância local

Atualizada em `http://127.0.0.1:8770`, após confirmar zero trabalhos ativos e gerar `cache/pre-multiarea-20261014-145400.sqlite3` com integridade SQLite verificada. Comparação completa das linhas da tabela de trabalhos antes/depois: **seis registros idênticos**. O aceite `scripts/qa_existing_readonly.cjs` passou com **zero requisições mutantes**, incluindo a apresentação honesta de três entregas históricas ausentes e o bloqueio de retomada sem arquivos de origem. Nenhuma dessas entregas antigas foi recriada ou removida.

## Product QA Guardrails

| Critério | Veredito | Tela/estado e evidência | Impacto e recomendação |
| --- | --- | --- | --- |
| Compreensão sem explicação compensatória | PASS | Contexto e revisão, cinco perfis, validação inline, teclado, screenshots desktop/mobile e uso no navegador | Assunto, público e perfil identificáveis; sem falha bloqueante. Manter os rótulos específicos. |
| Uma pergunta por tela | PASS | Inspeção do fluxo Gravações → Contexto → Revisão e abas Previews / Documentos / Pedido no navegador | Etapas têm decisões distintas; filtros de histórico ficam na mesma tela. Nenhuma consolidação necessária no escopo. |
| Vazios acionáveis | PASS | Histórico inicial com Criar primeira análise; busca/filtro sem resultados com Limpar filtros, exercitados no navegador | Há continuidade segura, sem beco sem saída. Manter as ações existentes. |
| Confirmações destrutivas específicas | PASS | Limpeza de falhas/cancelados: quantidade/escopo, irreversibilidade, Excluir esses trabalhos e cancelamento por botão/Escape; restauração de foco testada | Escopo explícito e saída segura. Nenhuma mudança adicional necessária. |

## Limites da validação

- Inferência de síntese, análise visual e transcrição foram simuladas. Qualidade editorial, precisão dos cortes e tempo de processamento com gravações reais ainda exigem uma execução real autorizada.
- Não foi feita chamada paga à API, integração Supabase ou OAuth real com Google Drive. Os testes de acesso não significam que o login corporativo já esteja conectado.
- Modo local permanece sem autenticação de integrantes; a configuração obrigatória continua bloqueando acesso enquanto o provedor não está implementado.
- Os testes não reprocessam nem substituem arquivos das análises existentes. Não houve commit, push ou publicação externa nesta entrega.
