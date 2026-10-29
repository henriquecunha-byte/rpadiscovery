# Contexto do Discovery: interface reutilizável

Recuperação do formulário demonstrado na reunião de 14/10/2026, com base nas telas entre 08:15 e 09:45. O formulário principal já está em `rpa_docs/static`; este diretório permite gerar uma referência funcional separada, sem carregar o backend Python, APIs, credenciais ou banco de dados.

## O que é reaproveitado

- Seis tipos de documentação: Personalizado, Reunião, Treinamento, Entrevista, Pesquisa e Processo / RPA.
- Assunto, objetivo e cliente/área condicionais ao perfil.
- Soluções combináveis, etapa de destino, público e checklist sugerido de entregáveis.
- Seleções manuais preservadas, sistemas em tags e orientação para dados sensíveis.
- Guia montado pelos campos, edição manual e confirmação antes de substituir edições.
- Revisão do pedido com categoria, itens selecionados, objetivo, sistemas e guia.

A preferência posterior por documentação com prints é mantida. O vídeo da reunião é evidência do comportamento, não uma instrução para remover melhorias aprovadas depois dela.

## Gerar e visualizar

Na raiz do repositório:

```powershell
.\.venv\Scripts\python.exe scripts\export_context_ui.py
.\.venv\Scripts\python.exe -m http.server 8773 --bind 127.0.0.1 --directory cache\context-ui-preview
```

Abra `http://127.0.0.1:8773/?perfil=processo` para o caminho demonstrado. Sem o parâmetro, o padrão permanece Personalizado. A saída em `cache/context-ui-preview` é um build de teste regenerável, não uma segunda fonte de regras.

O exportador copia somente HTML, JavaScript, CSS, regras JSON e três fontes da marca. Os caminhos de assets tornam-se relativos. Não importa a configuração da aplicação, não lê `.env` e não copia vídeos ou transcrições da reunião. Não é preciso instalar outro framework.

## Reaplicar no projeto Lovable existente

Use este material para atualizar apenas a etapa de contexto da interface existente. O projeto deve continuar responsável por sua autenticação, arquivos, IA, endpoints e persistência. Não substitua esses serviços pelo backend Python deste repositório.

O controlador público mantém os mesmos contratos do app:

```javascript
await window.DiscoveryContextForm.ready;
// Ao abrir um pedido existente, forneça o contexto recebido pelo próprio app:
window.DiscoveryContextForm.setValue(contextoDoPedido);

// Alterações de campos continuam emitindo discovery:contextchange.
// Confirmar na referência emite o pedido revisado, sem salvá-lo ou processá-lo:
document.addEventListener('discovery:requestready', event => {
    const { contexto, title, process_context, audience, detail_level } = event.detail;
    // Entregar esses valores ao estado/fluxo JÁ existente da aplicação hospedeira.
});
```

O evento é emitido no `document` da mesma página. Não há bridge automática para iframe ou React, nem `postMessage` entre origens. O exemplo ilustra o contrato; adaptar a montagem e o estado ao frontend real do Lovable é uma etapa distinta de integração. Os estilos completos são adequados à página isolada; em uma página existente, preserve os componentes e tokens do host para evitar estilos globais duplicados.

O botão de melhoria por IA, orçamento, aprovação de consumo, login, upload, Drive, fila e exportação de documentos ficam fora desta referência. O guia local funciona sem esses serviços. Não há `localStorage` ou persistência automática; ao confirmar, a aplicação hospedeira decide como usar o pedido.

**Limite:** a referência confirma o comportamento do formulário. Ela não publica alterações no Lovable nem executa uma análise de vídeo. O código de API e banco do projeto não é alterado pelo exportador.

## Arquivos e validação

- `scripts/export_context_ui.py`: gera a página com o formulário e as regras canônicas.
- `shell.html`, `context-preview.js` e `context-preview.css`: apresentação isolada e revisão.
- `scripts/qa_context_reconstruction.cjs`: testa a referência em desktop/celular e bloqueia qualquer chamada de serviço ou recurso externo.
- `scripts/qa_structured_context.cjs`: regressão do formulário no app original.
- `docs/RECONSTRUCAO-DISCOVERY-2026-10-29.md`: mapeamento da reunião, diferenças e QA.
