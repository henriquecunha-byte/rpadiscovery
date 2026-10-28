# Base de acesso ao Discovery

Status: estrutura implementada, autenticação real ainda indisponível. Nenhum projeto Supabase foi conectado e nenhuma conta foi criada. Não publique o aplicativo como ambiente autenticado nesta etapa.

## O que já existe

- Telas de login por e-mail/senha e recuperação, com identidade Btime, estados de indisponibilidade, carregamento e erro.
- Saída do ambiente: limpa dados da interface e rascunhos próprios do navegador, interrompe consultas e previews. Não cancela trabalhos no servidor.
- Modo local explicitamente sem autenticação para continuar os testes.
- Contrato de sessão e pontos de integração isolados no servidor, sem armazenar credenciais no navegador.
- Fronteira de API que bloqueia o modo protegido antes de ler uploads ou executar ações.
- Autorização por proprietário no banco e em todas as rotas de trabalhos/arquivos, pronta para receber a identidade verificada do futuro login. Veja [Privacidade por conta](USER-PRIVACY.md).

Não há cadastro público, senha de demonstração, token falso ou conta administrativa padrão. Os controles de login e recuperação permanecem indisponíveis enquanto o servidor informar `enabled: false`. A tela nunca afirma ter enviado recuperação sem uma resposta de sucesso do provedor futuro.

## Modos do ambiente

Configure o `.env` local e reinicie o servidor:

| Configuração | Comportamento |
| --- | --- |
| `AUTH_MODE=local` (padrão) | Área local aberta, sem separação entre pessoas que usam esse modo. Acesso apenas a trabalhos locais/legados sem dono, nunca aos trabalhos de contas. A entrada oferece **Continuar no ambiente local**. |
| `AUTH_MODE=required` | API bloqueada com HTTP 503 e código `auth_not_configured`. A interface não oferece acesso local. |
| Valor inválido ou vazio | Mesmo bloqueio do modo obrigatório; erro de configuração explícito. |

`SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY` estão reservados no `.env.example`. Preenchê-los muda apenas o estágio de configuração para `integration_pending`; **não ativa o login**. O adaptador precisa ser implementado e validado primeiro. Não use `service_role` ou secret key no cliente.

O modo local deve permanecer vinculado a `127.0.0.1` e não pode ser exposto à internet ou à rede da equipe. O botão Sair limpa a interface, mas não impede acesso direto à API local aberta. A barreira de segurança é o servidor, não a navegação da página.

## Contrato HTTP

Todas as respostas de autenticação usam `Cache-Control: no-store`.

| Endpoint | Resposta atual |
| --- | --- |
| `GET /api/auth/config` | `mode`, `provider`, `status`, `enabled: false`, `can_continue_local`, `message`; nenhuma chave exposta. |
| `GET /api/auth/session` | `authenticated: false`, `user: null` e estágio da integração. |
| `POST /api/auth/login` | 503 antes de ler e-mail ou senha. |
| `POST /api/auth/recover` | 503; nenhum e-mail enviado. |
| `POST /api/auth/logout` | 200 anônimo, remove o cookie reservado. Não representa revogação no Supabase, pois ainda não existe sessão do provedor. |

No modo obrigatório, só esses cinco pares exatos de método/caminho ficam públicos na API. As páginas e os assets de login permanecem públicos. Listagens, upload, ações, mídia, documentos, downloads, saúde e Google Drive são bloqueados; cookies e bearer tokens forjados não concedem acesso.

O cliente prepara formulários para `POST {email,password}` e `POST {email}`; a futura integração deve confirmar login por `GET /api/auth/session` retornando `{authenticated:true,user:{id,email}}`. O cliente não aceita um token informado no hash da página nem salva senha ou token em localStorage/sessionStorage. Rotas de retorno são somente hashes internos conhecidos. O fluxo real de recuperação e definição de nova senha ainda depende da integração.

## Etapa futura: conectar com segurança

1. Escolher e configurar o projeto Supabase, URLs de retorno e envio de e-mail. Definir quem convida integrantes; cadastro público não faz parte desta base.
2. Implementar o provedor de `rpa_docs/auth.py`: sessão real no servidor, validação criptográfica e de expiração/issuer/audience dos tokens, renovação e revogação. O cookie reservado não é uma sessão implementada.
3. Definir cookies HttpOnly/Secure/SameSite e proteção CSRF/origem para login e ações; limites de tentativas, mensagens neutras e política de sessão. Não colocar credenciais de infraestrutura no browser.
4. Implementar a conclusão da recuperação de senha e redirects permitidos (PKCE/fluxo apropriado ao servidor); não basta liberar o botão atual.
5. Conectar a identidade validada à autorização por proprietário já implementada. A conexão Google por conta ainda precisa de tokens/estado OAuth individuais; a conexão local fica bloqueada para contas. Não atribuir trabalhos legados automaticamente.
6. Aplicar RLS nas tabelas e Storage expostos pelo Supabase, usando identidade verificada; não autorizar com `user_metadata` editável pelo usuário.
7. Só então permitir `enabled: true`, substituir o bloqueio por verificação real e testar com contas separadas, sessão expirada, revogação, recuperação e tentativa de acesso a arquivos de outra equipe.

Referências oficiais consultadas: [Autenticação com senha](https://supabase.com/docs/guides/auth/passwords), [autenticação no servidor](https://supabase.com/docs/guides/auth/server-side) e [changelog](https://supabase.com/changelog).

## Validação reproduzível

Backend: `python -m unittest tests.test_auth -v` na virtualenv do projeto. A suíte verifica modos, respostas sem segredos, bloqueio antes de ler corpos, métodos/caminhos, downloads, configuração inválida e tokens forjados.

Interface: iniciar `scripts/qa_server.py` com `AUTH_MODE=local` e executar `node scripts/qa_auth.cjs` com Playwright disponível. Vídeos e dados são sintéticos, sem worker nem chamadas ao Supabase. Evidências ficam em `cache/auth-qa-evidence/` (ignorado no Git).

Os cenários de login/sessão/recuperação bem-sucedidos no teste de navegador usam **mocks explícitos de um provedor futuro**. Validam a interface, não provam autenticação real. Os cenários de indisponibilidade e modo local usam o servidor implementado.

Aceite local em 08/10/2026: 84 testes Python aprovados (incluindo 17 de autenticação), 16 cenários de acesso no Chrome e 47 cenários de regressão da interface. Telas inspecionadas em desktop e celular; a responsividade do login foi verificada de 320 a 1440 px. Nenhuma autenticação ou recuperação real no Supabase foi executada.

Após a base de login, foram adicionados testes de propriedade no banco/API e de troca de conta no navegador; consulte `tests/test_ownership_*` e `scripts/qa_context_privacy.cjs`. O aceite anterior descreve a primeira etapa, não substitui os novos testes.
