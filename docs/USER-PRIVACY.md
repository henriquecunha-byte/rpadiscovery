# Privacidade por conta

Implementação independente do provedor de login. Nenhum projeto, tabela, Storage ou usuário foi criado no Supabase. A autenticação real da empresa continua sendo uma etapa futura; até lá, `AUTH_MODE=required` bloqueia a API e `local` permanece uma área de testes sem login.

## Regra de propriedade

Cada análise tem `owner_id` persistido no SQLite. Upload, vídeos originais, previews separados, cortes, transcrição, evidências, documentos, ZIP, eventos e ações seguem o proprietário da análise.

| Origem do acesso | Visibilidade |
| --- | --- |
| Identidade verificada da conta A | Somente análises de A. |
| Identidade verificada da conta B | Somente análises de B. |
| Ambiente local sem login | Somente análises locais/legadas com `owner_id IS NULL`. |
| Modo obrigatório sem provedor | Nenhuma análise; API bloqueada. |

`NULL` não significa todos os usuários. Os trabalhos existentes permanecem locais e não são atribuídos à primeira conta que entrar. Nenhuma migração de propriedade ou compartilhamento entre contas é automático.

O ID do proprietário vem exclusivamente da identidade confirmada no servidor. Um campo no upload, query string, cookie inventado, bearer não verificado ou `X-User-Id` não escolhe o dono. A API atual não possui rota de transferência de propriedade.

## Proteções aplicadas

- Filtro de dono no SQL de listagem, detalhe, ações, limpeza, histórico de estimativas e posição entre os próprios pedidos.
- Conferência antes de enriquecer metadados, abrir arquivo, gerar PDF ou executar ação. Uma análise de outra conta retorna o mesmo 404 de uma análise inexistente.
- Checagem também nos links diretos: MP4, Range, prints, relatório, Word, PDF, JSON, CSV, Markdown, ZIP e gravação original. Arquivos não são publicados em `/static`.
- `Cache-Control: private, no-store` e variação por Cookie/Authorization nas respostas da API, inclusive arquivos parciais e erros.
- Caminhos de arquivos seguem a pasta correta da análise, sem aceitar symlink/junction restaurado que aponte para outra pasta. Pastas existentes não precisam ser movidas.
- Criação por caminho arbitrário do servidor é proibida para contas. No ambiente local, esse endpoint também rejeita referências à pasta interna de análises.
- Rascunhos e pasta do Drive são persistidos no navegador somente no modo local. Contas mantêm esses campos em memória e ignoram o rascunho legado. Trocar de identidade limpa a interface, encerra players, aborta requisições do cliente e descarta respostas antigas; não cancela o processamento no servidor.
- O worker pode processar a fila técnica global, internamente. A posição exibida é relativa aos pedidos visíveis da própria conta, não uma contagem dos trabalhos de outras pessoas.

## Google Drive

A integração atual usa credenciais locais compartilhadas. Por isso, o acesso de uma conta autenticada a essa conexão fica bloqueado: não é permitido listar, importar, exportar ou conectar usando os tokens do ambiente local. O status informa que a integração individual está pendente, sem expor a pasta padrão local.

O uso local atual é preservado. Para liberar Drive para contas da equipe, implementar tokens, estado OAuth e pasta padrão por identidade, mantendo a autorização da análise antes da exportação. Arquivos baixados ou exportados podem ser compartilhados fora do aplicativo por quem os recebeu; esta proteção não é DRM.

## Conectar o login corporativo depois

O ponto de entrada é `rpa_docs/access.py:current_access`. Somente após verificar uma sessão real, o adaptador deverá fornecer `request.state.verified_identity = VerifiedIdentity(user_id, session_id)`. Não construir essa identidade diretamente de dados enviados pelo cliente.

A barreira atual de `rpa_docs/auth.py` continua bloqueando o modo obrigatório. A futura integração deve substituir o bloqueio por verificação real, e não simplesmente removê-lo. Depois, validar sessão expirada, revogação, contas separadas e acesso por link. Se os dados/arquivos forem movidos do SQLite/disco para um serviço remoto, reproduzir a mesma política no banco e armazenamento, com arquivos privados.

Os overrides de identidade presentes nos testes existem apenas dentro do processo de teste. Não há header, flag HTTP, senha padrão ou variável de ambiente que permita se passar por uma conta.

## Testes reproduzíveis

Executar pela virtualenv do projeto:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ownership_database tests.test_ownership_api tests.test_auth -v
```

Cobertura: A/B/local, leitura e download por link, tentativa de alteração e limpeza de outra conta, proprietário forjado, migração idempotente, worker preservando o dono, cache, Range, caminhos codificados e resolução simulada de links/junctions (sem exigir privilégio de symlink do sistema).

No servidor sintético `scripts/qa_server.py`, executar `node scripts/qa_context_privacy.cjs` e `node scripts/qa_auth.cjs`. A troca de contas nesses cenários usa respostas de sessão simuladas; não valida login real.

Aceite em 08/10/2026: 134 testes Python aprovados e 68 cenários de navegador (35 gerais, 12 de bordas, 16 de login e 5 de contexto/privacidade). A checagem somente leitura no servidor local preservou os 4 trabalhos existentes; nenhuma análise real foi reenviada. A presença da configuração de IA foi confirmada após reinício, sem chamada paga para validar a credencial no provedor.
