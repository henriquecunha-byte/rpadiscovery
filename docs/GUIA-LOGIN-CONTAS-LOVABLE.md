# Discovery — guia de login, contas e gravações privadas

Preparado em: 29/10/2026.

## 1. Pedido para o Lovable

Implemente ou complete o login e o sistema de contas do Discovery para que **cada pessoa tenha acesso somente às próprias gravações, análises e entregáveis**. A proteção deve funcionar na interface, nos serviços, no banco e no acesso aos arquivos.

**Preserve o projeto Lovable Cloud, a API de IA e o banco de dados que já estão em uso.** Não crie outro backend, não substitua o banco pelo SQLite do repositório de referência, não troque provedores ou chaves e não recrie contas existentes.

Inspecione primeiro a autenticação, as tabelas, as políticas e o armazenamento atuais. Reaproveite os recursos existentes. Caso faltem vínculos de propriedade ou regras de acesso, apresente as alterações mínimas necessárias no mesmo banco; preserve os registros e a compatibilidade com o app. Este guia não autoriza apagar dados ou atribuir gravações antigas arbitrariamente.

O Cloud oferece autenticação, banco e armazenamento no backend do próprio projeto; não é necessário presumir uma nova infraestrutura para esta implementação. [Documentação do Lovable Cloud](https://docs.lovable.dev/features/cloud).

**Estado deste documento:** especificação para implementação. O projeto publicado ainda precisa ser inspecionado e validado. Testes locais com login simulado não comprovam autenticação real no Lovable.

## 2. Experiência de login e contas

### Acesso inicial e entrada

- Exibir uma tela de login com a identidade visual atual da Btime.
- Reutilizar os métodos já configurados. Se houver e-mail e senha, oferecer esses campos, mostrar/ocultar senha e recuperação de acesso. Não exibir um botão de Google ou SSO sem integração funcional.
- Permitir gerenciadores de senha, preenchimento automático, navegação por teclado e mensagens associadas aos campos.
- Mostrar estados de carregamento, falha de conexão e credenciais inválidas; impedir envios duplicados enquanto a solicitação estiver em andamento.
- Só liberar a área privada após confirmar uma sessão real. Uma variável no navegador ou uma resposta simulada não representa login.
- Ao abrir um endereço privado sem sessão, encaminhar ao login. Após entrar, retornar apenas a uma rota interna válida e conferir novamente a permissão daquele conteúdo.
- Não oferecer acesso anônimo ou “continuar no modo local” para contornar a proteção do app publicado.

Usar mensagens que não revelem se um e-mail possui conta, recuperação real pelo provedor e os controles de tentativas já disponíveis. Senhas e tokens de recuperação não devem aparecer em logs ou mensagens de erro. [Orientações de autenticação da OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html).

### Criação de contas

Proposta inicial para o uso interno da Btime: contas por convite ou liberação administrativa, evitando abrir cadastro público sem uma decisão do produto. Se já houver uma política aprovada no app, preservá-la e documentá-la.

- Reaproveitar o fluxo de convite/cadastro do provedor atual, incluindo confirmação de identidade quando exigida.
- Um convite deve ter validade e ser usado somente pelo destinatário autorizado, conforme o mecanismo do provedor.
- Validar admissão no backend. Esconder o botão de cadastro não impede cadastros por chamadas diretas.
- Nunca criar uma senha padrão compartilhada, conta administrativa automática ou aprovação baseada apenas em um e-mail informado pelo navegador.

### Recuperação, sessão e saída

- Recuperar e definir nova senha pelo fluxo real do provedor, tratando link inválido, expirado ou já utilizado.
- Confirmar a aceitação da solicitação antes de informar que a recuperação foi solicitada, sem revelar a existência da conta.
- Reutilizar o SDK e o mecanismo de sessão do projeto. Não criar autenticação própria nem armazenar senhas na tabela de perfil.
- Em sessão expirada, interromper o acesso privado e solicitar nova entrada. Não alternar para modo público.
- Em “Sair”, encerrar a sessão pelos meios oferecidos pelo provedor e limpar os dados privados da interface. Documentar se a saída encerra somente a sessão atual ou todas as sessões.
- Sair não apaga gravações e não cancela automaticamente análises já iniciadas.

## 3. Páginas e comportamento esperado

| Área | Comportamento |
| --- | --- |
| Login / recuperação | Entrar e recuperar acesso com o provedor real. |
| Minhas gravações / Minhas análises | Exibir apenas os registros autorizados da conta atual. Integrar à navegação existente, sem criar telas redundantes. |
| Nova análise | Associar automaticamente fontes e pedido ao usuário autenticado; não pedir que ele escolha o proprietário. |
| Detalhe da análise | Mostrar progresso, contexto, previews e documentos exclusivamente da análise autorizada. |
| Minha conta | Mostrar nome e e-mail da própria conta, método de alteração de senha quando aplicável e botão Sair. |
| Gestão de integrantes, se aplicável | Convidar ou desativar integrantes com permissão administrativa verificada no servidor. Não dar acesso automático às gravações privadas. |

Uma conta sem gravações deve ver uma mensagem como “Você ainda não enviou gravações” e uma ação “Adicionar gravação”. Falha ao carregar não deve ser apresentada como lista vazia. No menu, identificar a conta ativa para facilitar o uso em computadores compartilhados.

## 4. Regra central de propriedade

**O proprietário vem da identidade autenticada e verificada pelo serviço, nunca de um identificador escolhido pelo cliente.** Não usar nome, e-mail, pasta, cookie inventado, parâmetro da URL ou campo livre como prova de propriedade.

O princípio técnico é negar acesso sem permissão explícita e validar a autorização em toda operação, inclusive acesso direto a arquivos. Filtrar cartões no frontend não protege os dados. [Orientações de autorização da OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html).

### Modelo lógico — adaptar ao esquema existente

Os nomes abaixo são conceituais, não instruções para criar tabelas duplicadas:

| Recurso | Vínculo necessário |
| --- | --- |
| Conta autenticada | ID estável fornecido pelo provedor. |
| Perfil | Referência à conta; nome e preferências, sem senhas. |
| Gravação / upload | Proprietário e referência ao objeto privado no armazenamento. |
| Pedido / análise | Proprietário, contexto e referências às gravações autorizadas. |
| Documento, print, transcrição, corte, preview ou ZIP | Referência à análise/gravação que determina o acesso. |
| Eventos e progresso | Referência à análise; assinatura e consulta limitadas ao usuário autorizado. |

- Todos os arquivos enviados em lote, pasta ou ZIP devem seguir a mesma conta autenticada.
- Uma análise não pode referenciar uma gravação de outra conta por manipulação do ID.
- Reprocessar, duplicar ou retomar uma análise deve preservar o proprietário e verificar as fontes.
- A propriedade não deve ser editável pelo usuário. Validar tanto o registro existente quanto os novos valores em atualizações.
- Se os filhos também armazenarem o ID do dono, garantir que ele corresponda ao recurso pai. Não depender de duas informações que possam divergir.
- Se o banco já utiliza políticas por linha, aplicar a regra em leitura, criação, atualização e exclusão. Operações privilegiadas no backend precisam da mesma verificação explícita.

### Matriz de acesso

| Pessoa / processo | Conteúdo de A | Conteúdo de B |
| --- | --- | --- |
| Sem sessão válida | Negado | Negado |
| Usuário A | Permitido conforme a ação | Negado |
| Usuário B | Negado | Permitido conforme a ação |
| Administrador funcional do app | Sem acesso automático por ser administrador | Sem acesso automático por ser administrador |
| Processamento interno | Apenas os recursos necessários ao trabalho autorizado | Apenas os recursos necessários ao trabalho autorizado |

Compartilhamento entre colegas e transferência de propriedade ficam fora desta versão. Uma futura permissão de equipe deve ser explícita; pertencer à Btime não torna todas as gravações públicas entre integrantes. Essa matriz trata dos acessos do aplicativo, não redefine os privilégios técnicos dos operadores da infraestrutura.

## 5. Upload, arquivos e entregáveis

1. Validar a sessão antes de criar o registro de upload.
2. Reservar um destino privado associado à conta e à gravação.
3. Se houver upload direto para o armazenamento, limitar a autorização ao objeto e à operação previstos; não permitir trocar o destino para outra conta.
4. Ao concluir o upload, conferir novamente o vínculo do objeto antes de aceitá-lo para processamento.
5. Vincular os documentos, imagens, cortes e demais resultados ao mesmo pedido autorizado.

Gravações, prints e entregáveis não devem ficar em buckets públicos ou diretórios de assets públicos. Separar os caminhos por usuário ajuda na organização, mas não substitui a política de acesso.

Proteger também miniaturas, player, requisições parciais de vídeo, download individual, ZIP completo e versões antigas de documentos. Conhecer o ID ou o caminho do arquivo não pode conceder acesso.

**Links assinados:** uma URL temporária utilizável por qualquer portador não fica vinculada à identidade de quem a recebeu. Para cumprir o isolamento por conta mesmo ao copiar um endereço para outra sessão, preferir entrega por rota autenticada que confira a propriedade a cada solicitação. Caso o armazenamento use URLs assinadas internamente, não tratá-las como substitutas dessa verificação nem expor links reutilizáveis como acesso privado por conta.

Arquivos que a própria pessoa já baixou podem ser compartilhados por ela fora do app; o login não revoga cópias locais. O objetivo é impedir acesso indevido aos recursos mantidos pelo aplicativo.

## 6. Processamento, ações e troca de conta

- O worker deve obter o proprietário do pedido persistido e verificado, sem confiar em um ID de usuário fornecido livremente à função de processamento.
- Preservar o vínculo em filas, retentativas, callbacks e geração de novos arquivos. Não usar o usuário que estiver logado no navegador quando o trabalho terminar.
- Validar propriedade antes de cancelar, retomar, renomear, excluir, reutilizar ou exportar qualquer análise.
- “Limpar fila” deve operar somente sobre os registros permitidos da conta atual, respeitando os estados elegíveis já definidos no produto.
- Filtrar também busca, totais, histórico, notificações, eventos em tempo real e estimativas para não revelar nomes ou conteúdo de outras contas.
- Downloads privados e respostas de dados não devem ser reutilizados por um cache compartilhado entre usuários.

Na saída ou mudança de conta: encerrar players, limpar detalhes e listas, descartar rascunhos privados da identidade anterior, invalidar caches, interromper assinaturas de eventos e ignorar respostas atrasadas. Chaves de cache devem incluir a identidade. Se houver rascunhos persistidos, restaurar somente os do proprietário verificado.

O processamento pode continuar no servidor após a saída. A conta B não deve receber notificações ou resultados de um trabalho iniciado por A, mesmo usando a mesma aba depois.

## 7. Integrações e dados existentes

### Google Drive, se já estiver disponível

- Associar a conexão e seus tokens à identidade autorizada; não reutilizar automaticamente a conexão local ou a credencial de outro integrante.
- Conferir a propriedade antes de importar para um pedido, exportar entregáveis ou consultar arquivos.
- Se existir uma conexão corporativa de serviço, aplicar a autorização de cada usuário no app antes de usá-la.
- Não alterar permissões do Drive para tornar arquivos públicos. Permissões de arquivos exportados no Drive são independentes da privacidade dentro do app.

### Gravações anteriores ao login

- Preservar os proprietários já registrados e verificados.
- Registros sem proprietário não podem aparecer para todo usuário nem ser atribuídos à primeira pessoa que entrar.
- Manter legados sem dono fora das listagens privadas normais até existir um mapeamento confiável.
- Se for necessário associá-los, apresentar os registros e a regra de associação para uma ação administrativa deliberada e auditável. Não deduzir o dono pelo nome do arquivo ou por quem abriu a página.
- Não apagar registros antigos para fazer os testes passarem.

### Administração e desativação

Se houver gestão de integrantes, usar papéis confiáveis do backend. O usuário não pode promover a si mesmo editando o perfil ou enviando um campo de função.

Desativação deve bloquear novos acessos e encerrar ou invalidar sessões conforme o mecanismo suportado, incluindo credenciais de acesso ainda válidas. Não presumir que esconder o integrante na interface revogue sessões. A retenção ou exclusão definitiva dos arquivos exige uma política definida; não apagar dados automaticamente ao desativar uma conta.

## 8. Plano de implementação

1. **Mapear o projeto atual:** provedor de identidade, sessão, tabelas, vínculos, armazenamento, workers e métodos de acesso aos arquivos. Informar o que já existe.
2. **Definir a política de entrada:** preservar a política aprovada ou confirmar a proposta de convites. Identificar como serão administrados os integrantes.
3. **Aplicar o isolamento:** aproveitar os campos existentes e propor somente os vínculos e políticas faltantes, sem trocar o banco ou a API de IA.
4. **Conectar a experiência:** login real, recuperação, sessão, conta ativa, área privada e saída; reaproveitar as telas existentes.
5. **Cobrir todas as operações:** upload, análise, eventos, previews, arquivos, exportações, retomada, cancelamento e limpeza.
6. **Validar com duas contas reais de teste:** testar leitura e escrita com A e B e verificar sessão ausente, expirada e revogada.

Não copiar para o app publicado o modo local sem autenticação do repositório Python. A referência local serve para regras de produto; não comprova o estado da autenticação do projeto Lovable.

## 9. Critérios de aceite

Preparar duas contas de teste autorizadas, A e B, com gravações diferentes e sem dados sensíveis. Usar sessões separadas e também testar a troca de conta na mesma aba.

| Teste | Resultado esperado |
| --- | --- |
| Login, recuperação e retorno após atualizar a página | Funcionam com o provedor real, sem mocks. |
| Conta recém-criada | Lista vazia acionável; não recebe gravações antigas automaticamente. |
| Upload individual, pasta e ZIP por A | Fontes e resultados ficam vinculados a A. |
| B consulta lista, busca, totais e progresso | Não recebe conteúdo nem metadados privados de A. |
| B tenta abrir o detalhe e os arquivos de A por endereço ou ID | Acesso negado sem vazamento de conteúdo. |
| B tenta cancelar, retomar, editar, excluir ou limpar trabalhos de A | Operação negada; os registros de A permanecem intactos. |
| B envia um proprietário forjado ou associa uma gravação de A ao pedido de B | Requisição rejeitada ou campo ignorado com identidade correta; não cria vínculo cruzado. |
| Acessar diretamente banco/Storage com credencial comum de B, quando isso fizer parte da arquitetura | As políticas também impedem acessar os recursos de A. |
| Copiar endereço de vídeo, print, PDF, DOCX ou ZIP de A para a sessão de B ou uma janela anônima | Acesso privado continua protegido; nenhum link público contorna a regra. |
| A inicia uma análise, sai e B entra na mesma aba | Não aparecem cache, rascunho, player, evento ou resposta atrasada de A. |
| O processamento de A termina depois da troca de conta | Os resultados continuam pertencendo somente a A. |
| Sessão expirada ou revogada | Novas operações privadas são bloqueadas, sem acesso local de fallback. |
| Alteração de nome ou e-mail | Mantém a propriedade vinculada ao ID estável da conta. |
| Tentativa de autopromoção a administrador | Não concede privilégios. |
| Registros legados sem proprietário | Permanecem preservados e não são expostos às contas. |
| Regressão da análise e exportação | A API de IA, o banco e as entregas atuais continuam funcionando para o dono autorizado. |

Registrar PASS, FAIL ou NOT RUN com evidência e motivo. Esses testes são **planejados**, não executados por este documento. Testar apenas a aparência da tela de login não valida o isolamento.

## 10. Entrega esperada do Lovable

- Resumo do fluxo de login e da política de criação de contas.
- Relação dos componentes, serviços e políticas alterados, com confirmação de que o backend e o provedor atuais foram preservados.
- Explicação de como gravações e todos os seus derivados recebem e mantêm o proprietário.
- Resultado dos testes A/B, incluindo links diretos, operações de escrita e troca de conta.
- Pendências reais, como configuração de e-mail, convite, SSO ou associação dos legados, sem apresentar uma simulação como funcionalidade concluída.

**Resultado final:** cada integrante entra com sua própria conta, envia gravações e acessa exclusivamente suas análises, cortes, evidências e documentos, em qualquer dispositivo no qual se autentique.
