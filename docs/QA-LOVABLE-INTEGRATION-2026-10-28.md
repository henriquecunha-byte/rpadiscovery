# QA da integração Lovable — 28/10/2026

## Escopo e resultado

**PASS no escopo automatizado local.** O backend seleciona Lovable por padrão, preserva os contratos de guia, análise visual e síntese e não troca para a credencial OpenAI legada automaticamente. A integração real no projeto Lovable Cloud está **NOT RUN**. Não há veredito de prontidão de produção ou de migração de banco.

Os testes usaram `RPA_DATA_ROOT` temporário, credenciais fictícias e HTTP simulado. Nenhuma gravação real, saldo de IA, banco de produção ou conexão de Drive foi usado. O servidor da apresentação não foi reiniciado.

## Evidências

| ID | Verificação | Resultado e evidência |
| --- | --- | --- |
| E1 | Regressão Python | **PASS**: 232 testes, 22,616 s, zero falhas. `unittest.defaultTestLoader.discover('tests')` em diretório temporário. |
| E2 | Contexto JavaScript | **PASS**: 21 testes, zero falhas. `node --test tests/test_context_model.cjs`. |
| E3 | Contrato de IA | **PASS**: `tests/test_ai_provider.py`, 11 casos com SDK real e `httpx.MockTransport`. Confere `/v1/responses`, modelo, papéis, texto, imagem em base64 e fala adjacente. |
| E4 | Configuração e privacidade | **PASS**: `test_health_tracks_selected_ai_provider_without_exposing_credentials` em `tests/test_api.py`; provedor inválido ou sem chave retorna indisponibilidade, somente booleanos chegam à saúde da API. |
| E5 | Erros e conta de cobrança | **PASS**: E3 cobre 401, 402, 403, 429 e 500; não repete nem troca provedor. Chaves e corpo do erro sintético não aparecem em avisos ou logs capturados. |
| E6 | Higiene do patch | **PASS**: `git diff --check` sem erros. `.env` e `.claude/` não fazem parte da entrega. |
| E7 | Lovable Cloud real | **NOT RUN**: não houve chamada autenticada ao projeto publicado, deploy ou migração. Os mocks não validam credencial, permissões, saldo nem qualidade semântica do modelo em produção. |

## Outras disciplinas

- Funcional: **PASS** dentro de E1–E4; sem fluxo de produção fim a fim.
- Segurança: **PASS** nos limites específicos E4/E5 (separação de credenciais, destino fixo, falhas sanitizadas). Não é um pentest ou auditoria completa do produto.
- Visual e acessibilidade: **N/A** nesta alteração do adaptador e contratos de backend; nenhum componente visual foi modificado. A interface do app não foi revalidada nesta rodada.
- Performance: **NOT RUN** para latência, transcrição e consumo em produção. A duração de testes locais não é uma medida de performance do serviço.

## Product QA Guardrails

Skills `product-qa-guardrails` e guia FAST lidos antes do veredito. Objetivo desta alteração: permitir ao servidor usar a IA do Lovable sem exigir uma conta OpenAI direta e sem modificar o fluxo de quem envia uma gravação. Não houve interface de usuário no escopo de implementação/teste desta rodada.

| Critério | Resultado | Evidência e limite |
| --- | --- | --- |
| Clareza | **N/A** | Adaptador de backend; nenhuma tela ou tarefa visual avaliada. |
| Telas redundantes | **N/A** | Nenhuma rota de navegação ou tela adicionada/alterada. |
| Estados vazios acionáveis | **N/A** | Sem estados visuais no escopo; indisponibilidade da IA testada apenas no contrato HTTP/pipeline, E3–E5. |
| Confirmações destrutivas específicas | **N/A** | A alteração não inclui ações destrutivas nem migra dados. |
| Complexidade proporcional / FAST | **N/A** | Configuração central de servidor, sem novo passo para o usuário. Não foi percorrida nem cronometrada uma tarefa visual. |

Esses N/A são do escopo desta alteração, não um aceite das telas do aplicativo. Um QA completo do produto deve exercitar os cinco critérios na interface real.
