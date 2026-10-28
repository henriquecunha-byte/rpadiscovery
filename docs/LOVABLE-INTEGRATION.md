# Discovery: Lovable AI e limite do backend local

Atualizado em 28/10/2026. Repositório: `henriquecunha-byte/rpadiscovery`.

## O que este código executa

As três operações de IA — melhoria do guia, análise visual e síntese dos documentos/cortes — usam a configuração central em `rpa_docs/ai.py`. O padrão é o gateway Lovable, pelo endpoint `https://ai.gateway.lovable.dev/v1/responses`. Texto, mensagens com papéis e imagens continuam no contrato Responses usado pelo pipeline.

O SDK Python `openai` é o cliente de protocolo. Com `AI_PROVIDER=lovable`, o destino e a credencial são do Lovable; não é uma chamada direta à conta OpenAI.

| Configuração do servidor | Uso |
| --- | --- |
| `AI_PROVIDER=lovable` | Padrão; seleciona somente o gateway Lovable. |
| `LOVABLE_API_KEY` | Segredo de projeto usado no servidor. Nunca no navegador, nos logs ou no Git. |
| `LOVABLE_MODEL=openai/gpt-5.6-luna` | Modelo padrão, mantendo a família anterior. Pode ser substituído por um modelo com texto/imagens e suporte a Responses disponível no projeto. |
| `AI_PROVIDER=openai` | Compatibilidade explícita com o backend local legado. Usa somente `OPENAI_API_KEY` e `OPENAI_MODEL`. |

No Lovable Cloud, o próprio projeto gerencia a credencial de IA. Este processo Python não recebe automaticamente os segredos de outro ambiente: a operação depende de provisionamento no servidor que executa o worker. Uma chave de workspace da API de gerenciamento do Lovable não substitui a chave de IA do projeto. Não copie credenciais para o código nem para variáveis públicas.

Uma chave antiga da OpenAI não habilita o modo Lovable. Não há fallback entre contas, provedores ou modelos, inclusive em falhas 401, 402, 403, 429 e 5xx. Cada chamada tem timeout de 120 segundos e não é repetida automaticamente pelo SDK. A retomada continua sendo uma ação explícita da análise. Falta de créditos gera orientação segura nos avisos do processamento; o botão de melhoria de guia preserva seu contrato neutro de indisponibilidade.

`GET /api/health` informa somente se existe a credencial do provedor selecionado. Esse booleano não comprova validade da chave, saldo, permissão do modelo ou funcionamento do Cloud.

## Banco, arquivos e Lovable Cloud

Este checkout continua com **SQLite** em `data/rpa_docs.sqlite3` (ou abaixo de `RPA_DATA_ROOT`), fontes e entregas em `jobs/`, transcrição local, FFmpeg e worker Python. A integração de autenticação desta versão continua pendente; `AUTH_MODE=required` bloqueia o acesso enquanto ela não existe. Selecionar Lovable AI não ativa login, banco ou armazenamento remoto.

O Lovable Cloud utilizado pelo produto é outro ambiente. O checkout atual não contém sua configuração nem uma implementação que substitua SQLite, arquivos ou autenticação pelo Cloud. O push desta alteração sincroniza código; não comprova deploy, migração ou publicação.

Para unificar a execução no Cloud, o próximo trabalho precisa usar a configuração real do projeto e contemplar:

1. Identificar o backend e o fluxo de publicação vinculados ao Discovery.
2. Implementar persistência de análises e propriedade por usuário no banco do Cloud, com migração e conferência dos registros existentes.
3. Integrar autenticação real e validar isolamento de análises, evidências e downloads entre contas.
4. Transferir fontes/entregas para armazenamento privado com acesso autorizado e política de retenção.
5. Definir a execução de transcrição, FFmpeg e exportações, incluindo fila, cancelamento e retomada. Não presumir que um worker Python local será executado só por estar no Git.
6. Validar uma análise completa no projeto publicado antes de considerar a migração concluída.

Nenhum banco, arquivo, segredo ou sessão de produção foi migrado por esta alteração. O `.env` local existente permanece preservado; sem a credencial Lovable nesse ambiente, a IA local informa indisponibilidade.

## Referências e validação

- [Lovable: IA do projeto e gestão da credencial](https://docs.lovable.dev/features/ai).
- [Lovable: modelos de texto e imagem](https://docs.lovable.dev/features/ai-chat).
- [TanStack AI: protocolo Responses e endpoint do gateway Lovable](https://tanstack.com/ai/latest/docs/adapters/lovable).
- [Lovable: backend integrado](https://docs.lovable.dev/features/cloud).

A validação automatizada está em `tests/test_ai_provider.py` e `tests/test_api.py`: serialização real do SDK sobre HTTP simulado, sem gravações reais nem créditos de IA. O relatório desta alteração registra o escopo e os limites em [QA Lovable](QA-LOVABLE-INTEGRATION-2026-10-28.md).
