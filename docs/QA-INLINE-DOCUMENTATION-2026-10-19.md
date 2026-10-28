# Leitor integrado de documentação — 19/10/2026

## Entrega

A documentação completa fica na aba Documentação, em HTML nativo do aplicativo, sem iframe, PDF obrigatório ou download automático. O índice navega dentro do documento e preserva a rota da análise. Os prints aparecem junto das etapas/itens; referências repetidas levam à figura já mostrada. O guia original permanece identificado como orientação, não como fato confirmado.

O layout preserva a identidade Btime. A skill better-layout orientou a separação entre leitura, índice e exportações; o progresso de uma análise já concluída não compete com o documento nesta aba. Os seis perfis mantêm sua estrutura específica, sem impor o modelo RPA a reuniões ou outros contextos.

PDF e ZIP são ações explícitas. A exportação PDF usa um snapshot dos dados e imagens salvos. O ZIP mantém os formatos disponíveis da entrega. Uma versão divergente é recusada com orientação para atualizar/revisar, sem trocar silenciosamente o conteúdo. Um manifesto existente também deve corresponder aos hashes das imagens exportadas.

Não foram executadas chamadas a IA, transcrição, OAuth ou contas externas. Nenhuma análise real foi reprocessada. Somente o ZIP da demonstração fictícia foi atualizado para incluir seus quatro PNGs; o anterior foi preservado em cache.

## Evidências e resultados

| Verificação | Resultado | Evidência |
| --- | --- | --- |
| Backend completo | PASS, 220/220 | `cache/inline-reader-python-tests.log`, unittest discovery |
| Leitor no Chrome | PASS, 24/24 | `scripts/qa_documentation_reader.cjs`, `cache/inline-reader-qa/results.json` |
| Regressão de autenticação local/futura simulada | PASS, 16/16 | `scripts/qa_auth.cjs`, `cache/auth-qa-evidence/` — nenhuma conta externa |
| Fluxo documental estático | PASS, 6/6 | `scripts/qa_static_documents.cjs`, `cache/static-document-ui-qa/`; ações Drive simuladas, sem OAuth/envio real |
| Modelo de contexto no navegador/Node | PASS, 21/21 | `node --test tests/test_context_model.cjs` |
| Demonstração no servidor real local | PASS, 6 verificações | `scripts/qa_demo_reembolsos.cjs`, `cache/demo-reembolsos-20261019/qa/results.json`; apenas GET/HEAD |
| Layout e teclado | PASS no escopo exercitado | 320, 390, 720, 1024 e 1440 px sem overflow; foco nas seções, alt das figuras, rótulos longos e espelhamento RTL |
| PDF da demonstração | PASS | 9 páginas, 4 imagens incorporadas; página 4 renderizada e inspecionada, com imagem proporcional e legenda legível |
| ZIP da demonstração | PASS | Integridade de todas as entradas; PDF, DOCX, HTML, Markdown, JSON, CSV e 4 PNGs presentes |

Casos do leitor: seis perfis; erro inicial com nova tentativa; exportação 503 recuperável; conflito 409; navegação atrasada sem sobrescrever outra análise; polling sem reconstruir o documento ou perder a rolagem; texto não interpretado como markup; nenhuma página ou download aberto automaticamente.

Os testes de API verificam isolamento entre proprietários antes da leitura de arquivos, mudanças no documento e nas imagens, pacote divergente, compatibilidade de legados, PDF com evidências exclusivas de regras de negócio e exportação sem modificar as entregas originais.

## Product QA Guardrails

Escopo: aba Documentação, índice, estados de carregamento/falha e ações PDF/ZIP. Evidência de runtime no Chrome, com dados sintéticos.

| Critério | Resultado | Evidência, impacto e recomendação |
| --- | --- | --- |
| Compreensão pela hierarquia e controles | PASS | Documento visível, título e público identificados; “Exportar PDF” e “Baixar ZIP” separados da leitura. Sem ambiguidade bloqueante observada; nenhuma correção adicional indicada. |
| Uma pergunta por tela | PASS | Documentação responde ao resultado; Pedido original preserva o brief; Atividade mostra execução; Vídeos oferece os cortes. Exportações são controles no leitor, não uma rota redundante. |
| Estados vazios acionáveis | PASS | Falha de leitura oferece “Tentar novamente”; conflito indica “Atualizar documento”; falha de PDF mantém ZIP disponível; vídeos não solicitados oferecem “Abrir documentação”. Nenhuma busca/filtro novo neste leitor. |
| Confirmações destrutivas específicas | N/A | O novo fluxo só lê ou exporta; não introduz nem exerce exclusão, sobrescrita ou revogação. |

## Limites do veredito

- Não é uma certificação WCAG, auditoria de segurança completa ou benchmark de performance. Foram exercitados teclado, alternativas das imagens, escape de conteúdo, propriedade e reflow; não foi feita uma nova auditoria integral de contraste ou zoom de navegador a 200%.
- O aplicativo não possui tema escuro. Não se reporta aprovação de um tema inexistente.
- O gate `scripts/accuracy_report.mjs` e as referências auxiliares da design-doctrine não estão instalados; nenhuma nota foi inventada. A verificação usa testes e inspeção visual registrados acima.
- Word não teve nova inspeção visual: o renderizador de Office não está instalado. A estrutura dos arquivos existentes é coberta por testes; essa limitação não impede o leitor nativo ou o PDF exportado.
- A revisão semântica de reuniões reais, seleção de evidências e conexão futura com serviços corporativos continuam dependências próprias; este trabalho não as declara concluídas.

Servidor local preservado em `http://127.0.0.1:8770/`, demonstração `#job=demo-reembolsos-f1e25cb6`. Nenhum commit, push ou deploy nesta rodada.
