/* Native, accessible context controls. Rules and draft migration live in context-model.js. */
(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    const model = window.DiscoveryContextModel;
    let value = null, guideOpen = false, busy = false, ready = false;
    const groupNames = ['solucoes', 'etapaDestino', 'publico', 'entregaveis'];
    const textNames = ['cliente', 'processo', 'objetivo', 'publicoOutro', 'instrucoesExtras'];
    const validationOrder = ['cliente', 'processo', 'solucoes', 'etapaDestino', 'publico', 'publicoOutro', 'entregaveis', 'context'];
    const controls = group => [...document.querySelectorAll('#' + group + ' input[name="' + group + '"]')];
    const selected = group => controls(group).filter(input => input.checked).map(input => input.value);
    const clone = object => JSON.parse(JSON.stringify(object));
    const profileChoices = new Map();
    const bridge = {
        ready: null,
        getValue: () => clone(value || {}),
        setValue,
        reset: () => setValue(model.defaultContext()),
        validate,
        getLegacyFields,
        getSummary,
        setGuide,
        setBusy(next) { busy = Boolean(next); renderAiState(); },
    };
    window.DiscoveryContextForm = bridge;

    function notify() {
        document.dispatchEvent(new CustomEvent('discovery:contextchange', { bubbles: true, detail: { contexto: bridge.getValue() } }));
    }
    function reconcile() {
        if (!model.isGeneral(value) && !value.etapaDestinoTocado && value.solucoes.length === 1 && value.solucoes[0] === 'rpa') {
            value.etapaDestino = 'spec_rpa';
        }
        if (!value.entregaveisTocado) value.entregaveis = model.suggestDeliverables(value);
        if (!value.guiaEditado) value.guia = model.compileGuide(value);
    }
    function change() {
        reconcile();
        render();
        notify();
    }
    function setValue(context) {
        if (!ready) return false;
        profileChoices.clear();
        const draft = model.migrateDraft({ version: 2, contexto: context });
        value = draft ? draft.contexto : model.defaultContext();
        reconcile();
        textNames.forEach(name => { $(name).value = value[name] || ''; });
        $('sistemas').value = '';
        $('sistemasStatus').textContent = '';
        guideOpen = false;
        busy = false;
        $('guideResetConfirmation').hidden = true;
        validationOrder.forEach(clearError);
        $('promptHint').textContent = 'Melhorar com IA usa a API configurada e pode gerar consumo. O guia gerado pelos campos não usa IA.';
        render();
        renderTags();
        return Boolean(draft);
    }
    function render() {
        if (!ready) return;
        const general = model.isGeneral(value), profile = model.rules.profiles[value.perfil];
        $('perfil').value = value.perfil;
        $('modoEntrega').value = value.modoEntrega;
        $('profileDescription').textContent = profile.description;
        $('clienteLabel').textContent = general ? 'Área ou projeto' : 'Cliente';
        $('clienteRequirement').textContent = general ? 'opcional' : 'obrigatório';
        $('cliente').required = !general;
        $('processoLabel').textContent = general ? 'Assunto da análise' : 'Nome do processo';
        $('processo').placeholder = general ? 'Ex.: Planejamento da campanha de lançamento' : 'Ex.: Gestão de pedidos';
        $('objetivoLabel').textContent = general ? 'O que você quer obter deste material?' : 'Por que esse processo está sendo mapeado?';
        $('objetivo').placeholder = general ? 'Ex.: registrar as decisões e as pendências para compartilhar com a equipe' : 'Ex.: reduzir a cópia manual de pedidos';
        $('solucoes').hidden = $('etapaDestino').hidden = general;
        controls('etapaDestino').forEach(input => { input.required = !general; input.disabled = general; });
        $('generalDetail').hidden = !general;
        $('detalhamento').value = value.detalhamento;
        $('sistemasLabel').textContent = general ? 'Termos e ferramentas de referência' : 'Sistemas envolvidos';
        $('sistemas').placeholder = general ? 'Digite um termo e pressione Enter' : 'Digite um sistema e pressione Enter';
        $('sistemasHelp').textContent = general ? 'Nomes, siglas e ferramentas que ajudam a interpretar o conteúdo. Enter ou vírgula adiciona; até 15 itens.' : 'Ajuda a análise a reconhecer as telas. Enter ou vírgula adiciona; até 15 sistemas.';
        const available = general ? profile.available : Object.keys(model.labels.entregaveis).filter(key => !model.rules.profiles.personalizado.available.includes(key));
        controls('entregaveis').forEach(input => { input.closest('label').hidden = !available.includes(input.value); input.disabled = !available.includes(input.value); });
        controls('publico').forEach(input => { input.closest('label').hidden = general && ['rpa', 'squad_ia', 'dev_flow'].includes(input.value) && !value.publico.includes(input.value); });
        groupNames.forEach(group => controls(group).forEach(input => {
            input.checked = group === 'etapaDestino' ? value.etapaDestino === input.value : value[group].includes(input.value);
        }));
        const other = value.publico.includes('outro');
        $('publicoOutroField').hidden = !other;
        $('publicoOutro').required = other;
        if (!other) clearError('publicoOutro');
        $('entregaveisChoices').hidden = !general && !value.etapaDestino;
        $('entregaveisHelp').textContent = !general && !value.etapaDestino ? 'Escolha a etapa acima para sugerirmos os itens.' : value.entregaveisTocado ? 'Itens personalizados por você. Use a sugestão para voltar à seleção recomendada.' : 'Sugestão para o perfil escolhido. Ajuste os itens se precisar.';
        $('resetDeliverables').hidden = (!general && !value.etapaDestino) || !value.entregaveisTocado;
        $('etapaSuggestion').hidden = value.etapaDestinoTocado || value.etapaDestino !== 'spec_rpa' || value.solucoes.length !== 1 || value.solucoes[0] !== 'rpa';
        $('dadosSensiveis').checked = value.dadosSensiveis;
        $('dadosSensiveis').setAttribute('aria-checked', String(value.dadosSensiveis));
        $('dadosSensiveisHelp').hidden = !value.dadosSensiveis;
        $('objetivoCount').textContent = value.objetivo.length.toLocaleString('pt-BR') + ' / 400';
        $('instrucoesExtrasCount').textContent = value.instrucoesExtras.length.toLocaleString('pt-BR') + ' / 1.500';
        $('contextCount').textContent = value.guia.length.toLocaleString('pt-BR') + ' / 8.000';
        if ($('context').value !== value.guia) $('context').value = value.guia;
        $('context').readOnly = !value.guiaEditado;
        $('context').required = value.guiaEditado;
        $('guideMode').textContent = value.guiaEditado ? 'Edição manual' : 'Gerado automaticamente';
        $('guideEditedNotice').hidden = !value.guiaEditado;
        $('editGuide').hidden = value.guiaEditado;
        $('toggleGuide').setAttribute('aria-expanded', String(guideOpen));
        $('toggleGuide').textContent = guideOpen ? 'Fechar' : 'Abrir';
        $('guidePanel').hidden = !guideOpen;
        renderAiState();
    }
    function renderAiState() {
        if (!ready) return;
        const available = Boolean(value.processo.trim() && (model.isGeneral(value) || value.cliente.trim()));
        $('suggestPrompt').disabled = busy || !available;
        $('suggestPrompt').setAttribute('aria-busy', String(busy));
        $('suggestPromptHelp').title = available ? '' : 'Preencha os campos obrigatórios do assunto primeiro.';
        $('suggestPromptRequirement').textContent = 'Preencha os campos obrigatórios do assunto primeiro.';
        $('suggestPromptRequirement').hidden = available;
    }
    function getLegacyFields() {
        if (!ready) return { title: '', process_context: '', audience: '', detail_level: 'operacional' };
        return {
            title: value.processo.trim(),
            process_context: value.guia.trim(),
            audience: model.audienceLabel(value),
            detail_level: model.isGeneral(value) ? value.detalhamento : value.etapaDestino === 'desenho' ? 'resumido' : 'operacional',
        };
    }
    function getSummary() {
        if (!ready) return [];
        const list = (name, values) => Object.keys(model.labels[name]).filter(key => values.includes(key)).map(key => model.labels[name][key]).join(', ');
        if (model.isGeneral(value)) return [
            ['Perfil', model.rules.profiles[value.perfil].label], ['Assunto', value.processo],
            ['Entrega', value.modoEntrega === 'documentacao' ? 'Documentação com prints' : 'Documentação com prints e vídeos com cortes'],
            ['Área ou projeto', value.cliente || 'Não informado'], ['Quem vai ler', model.audienceLabel(value)],
            ['Itens que a análise vai entregar', list('entregaveis', value.entregaveis)],
        ];
        return [
            ['Perfil', model.rules.profiles[value.perfil].label],
            ['Entrega', value.modoEntrega === 'documentacao' ? 'Documentação com prints' : 'Documentação com prints e vídeos com cortes'],
            ['Cliente', value.cliente], ['Processo', value.processo],
            ['Solução em vista', list('solucoes', value.solucoes)],
            ['Etapa', model.labels.etapas[value.etapaDestino] || 'Não informada'],
            ['Quem vai ler', model.audienceLabel(value)],
            ['Itens que a análise vai entregar', list('entregaveis', value.entregaveis)],
        ];
    }
    function setGuide(text, options = {}) {
        if (!ready || typeof text !== 'string' || text.length > 8000) return false;
        value.guiaEditado = options.edited !== false;
        value.guia = value.guiaEditado ? text : model.compileGuide(value);
        guideOpen = true;
        $('guideResetConfirmation').hidden = true;
        clearError('context');
        render();
        notify();
        return true;
    }
    function validationMessage(name) {
        switch (name) {
            case 'cliente': return model.isGeneral(value) || value.cliente.trim() ? '' : 'Informe o cliente.';
            case 'processo': return value.processo.trim() ? '' : 'Informe o assunto da análise.';
            case 'solucoes': return model.isGeneral(value) || value.solucoes.length ? '' : 'Escolha ao menos uma opção, ou "Ainda não definido".';
            case 'etapaDestino': return model.isGeneral(value) || value.etapaDestino ? '' : 'Escolha para qual etapa é esse material.';
            case 'publico': return value.publico.length ? '' : 'Escolha quem vai ler.';
            case 'publicoOutro': return !value.publico.includes('outro') || value.publicoOutro.trim() ? '' : 'Diga quem é o público.';
            case 'entregaveis': return value.entregaveis.length ? '' : 'Marque ao menos um item.';
            case 'context': return value.guiaEditado && !value.guia.trim() ? 'O guia não pode ficar vazio.' : '';
            default: return '';
        }
    }
    function clearError(name) {
        const message = $(name + 'Error');
        if (message) { message.textContent = ''; message.hidden = false; }
        const group = groupNames.includes(name);
        (group ? [$(name), ...controls(name)] : [$(name)]).filter(Boolean).forEach(element => element.removeAttribute('aria-invalid'));
    }
    function validateField(name) {
        const error = validationMessage(name), message = $(name + 'Error');
        if (message) { message.textContent = error; message.hidden = false; }
        (groupNames.includes(name) ? [$(name), ...controls(name)] : [$(name)]).forEach(element => {
            if (error) element.setAttribute('aria-invalid', 'true');
            else element.removeAttribute('aria-invalid');
        });
        return !error;
    }
    function validate(options = {}) {
        if (!ready) return false;
        flushSystem();
        const invalid = validationOrder.filter(name => !validateField(name));
        if (invalid.length && options.focus !== false) {
            const name = invalid[0];
            if (name === 'context') { guideOpen = true; render(); }
            const target = groupNames.includes(name) ? controls(name)[0] : $(name);
            target?.scrollIntoView({ block: 'center', behavior: 'instant' });
            target?.focus({ preventScroll: true });
        }
        return !invalid.length;
    }
    function renderTags() {
        const list = $('systemTags');
        list.replaceChildren();
        value.sistemas.forEach((name, index) => {
            const item = document.createElement('li'), label = document.createElement('span'), remove = document.createElement('button');
            label.textContent = name;
            remove.type = 'button';
            remove.setAttribute('aria-label', 'Remover ' + name);
            remove.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>';
            remove.addEventListener('click', () => {
                value.sistemas.splice(index, 1);
                renderTags();
                change();
                $('sistemasStatus').textContent = name + ' removido.';
                const remaining = [...list.querySelectorAll('button')];
                (remaining[Math.min(index, remaining.length - 1)] || $('sistemas')).focus();
            });
            item.append(label, remove);
            list.append(item);
        });
    }
    function addSystem(raw) {
        const name = raw.trim();
        if (!name) return true;
        if (name.length > 80) { $('sistemasStatus').textContent = 'Use até 80 caracteres por sistema.'; return false; }
        if (value.sistemas.some(item => item.toLocaleLowerCase('pt-BR') === name.toLocaleLowerCase('pt-BR'))) {
            $('sistemasStatus').textContent = 'Esse sistema já foi adicionado.';
            return true;
        }
        if (value.sistemas.length >= 15) { $('sistemasStatus').textContent = 'Você pode adicionar até 15 sistemas. Remova um para incluir outro.'; return false; }
        value.sistemas.push(name);
        $('sistemasStatus').textContent = name + ' adicionado. ' + value.sistemas.length + ' de 15 sistemas.';
        renderTags();
        change();
        return true;
    }
    function flushSystem() {
        const input = $('sistemas');
        if (!input.value.trim()) return;
        const remaining = input.value.split(',').filter(part => !addSystem(part));
        input.value = remaining.join(', ');
    }
    bridge.ready = model.ready.then(() => {
        function addChoice(group, key, label, className, parent) {
            const wrapper = document.createElement('label'), input = document.createElement('input'), span = document.createElement('span');
            wrapper.className = className; input.type = 'checkbox'; input.name = group; input.value = key;
            input.setAttribute('aria-describedby', group + 'Error'); span.textContent = label;
            wrapper.append(input, span); parent.append(wrapper);
        }
        Object.entries(model.rules.profiles).forEach(([key, profile]) => {
            const option = document.createElement('option'); option.value = key; option.textContent = profile.label; $('perfil').append(option);
        });
        ['equipe','gestao','participantes','alunos'].forEach(key => addChoice('publico', key, model.labels.publico[key], 'context-chip', $('publico').querySelector('.context-chips')));
        ['alunos','participantes','gestao','equipe'].forEach(key => {
            const label = controls('publico').find(input => input.value === key).closest('label');
            label.parentElement.prepend(label);
        });
        model.rules.profiles.personalizado.available.forEach(key => addChoice('entregaveis', key, model.labels.entregaveis[key], 'context-check', $('entregaveisChoices')));
        ready = true;
        value = model.defaultContext();
        setValue(value);
        $('perfil').addEventListener('change', () => {
            profileChoices.set(value.perfil, {entregaveis: [...value.entregaveis], touched: value.entregaveisTocado});
            value.perfil = $('perfil').value;
            const saved = profileChoices.get(value.perfil);
            value.entregaveis = saved ? saved.entregaveis : model.suggestDeliverables(value);
            value.entregaveisTocado = saved ? saved.touched : false;
            validationOrder.forEach(clearError);
            if (value.guiaEditado) guideOpen = true;
            change();
        });
        $('detalhamento').addEventListener('change', () => { value.detalhamento = $('detalhamento').value; change(); });
        $('modoEntrega').addEventListener('change', () => { value.modoEntrega = $('modoEntrega').value; change(); });
        textNames.forEach(name => {
            $(name).addEventListener('input', () => { value[name] = $(name).value; change(); });
            if (validationOrder.includes(name)) $(name).addEventListener('blur', () => {
                if (!$('step2').hidden && !$(name).closest('[hidden]')) validateField(name);
            });
        });
        $('solucoes').addEventListener('change', event => {
            const input = event.target;
            if (input.name !== 'solucoes') return;
            let next = selected('solucoes');
            if (input.checked) next = input.value === 'indefinido' ? ['indefinido'] : next.filter(item => item !== 'indefinido');
            value.solucoes = next;
            change();
            if (!$('step2').hidden) validateField('solucoes');
        });
        $('etapaDestino').addEventListener('change', event => {
            if (event.target.name !== 'etapaDestino') return;
            value.etapaDestino = event.target.value;
            value.etapaDestinoTocado = true;
            change();
            if (!$('step2').hidden) validateField('etapaDestino');
        });
        $('publico').addEventListener('change', event => {
            if (event.target.name !== 'publico') return;
            value.publico = selected('publico');
            change();
            if (!$('step2').hidden) validateField('publico');
        });
        $('entregaveis').addEventListener('change', event => {
            if (event.target.name !== 'entregaveis') return;
            value.entregaveis = selected('entregaveis');
            value.entregaveisTocado = true;
            change();
            if (!$('step2').hidden) validateField('entregaveis');
        });
        groupNames.forEach(name => $(name).addEventListener('focusout', event => {
            if (!$('step2').hidden && !$(name).contains(event.relatedTarget)) validateField(name);
        }));
        $('resetDeliverables').addEventListener('click', () => {
            value.entregaveisTocado = false;
            change();
            validateField('entregaveis');
            controls('entregaveis')[0]?.focus();
        });
        $('dadosSensiveis').addEventListener('change', () => {
            // TODO: redaction of media/transcripts is not implemented; this flag only guides the analysis.
            value.dadosSensiveis = $('dadosSensiveis').checked;
            change();
        });
        $('sistemas').addEventListener('keydown', event => {
            if (event.isComposing) return;
            if (event.key === 'Enter' || event.key === ',') { event.preventDefault(); flushSystem(); }
            else if (event.key === 'Backspace' && !$('sistemas').value && value.sistemas.length) {
                const removed = value.sistemas.pop();
                renderTags();
                change();
                $('sistemasStatus').textContent = removed + ' removido.';
            }
        });
        $('sistemas').addEventListener('input', () => {
            const input = $('sistemas');
            if (!input.value.includes(',')) return;
            const parts = input.value.split(','), tail = parts.pop(), remaining = parts.filter(part => !addSystem(part));
            input.value = [...remaining, tail].join(',');
        });
        $('sistemas').addEventListener('blur', flushSystem);
        $('toggleGuide').addEventListener('click', () => {
            guideOpen = !guideOpen;
            $('guideResetConfirmation').hidden = true;
            render();
        });
        $('editGuide').addEventListener('click', () => {
            value.guiaEditado = true;
            render();
            notify();
            $('context').focus();
        });
        $('context').addEventListener('input', () => {
            if (!value.guiaEditado) return;
            value.guia = $('context').value;
            render();
            notify();
        });
        $('context').addEventListener('blur', () => { if (!$('step2').hidden) validateField('context'); });
        $('restoreGeneratedGuide').addEventListener('click', () => {
            $('guideResetConfirmation').hidden = false;
            $('cancelGuideReset').focus();
        });
        $('cancelGuideReset').addEventListener('click', () => {
            $('guideResetConfirmation').hidden = true;
            $('restoreGeneratedGuide').focus();
        });
        $('confirmGuideReset').addEventListener('click', () => {
            setGuide('', { edited: false });
            $('editGuide').focus();
        });
        $('guideResetConfirmation').addEventListener('keydown', event => {
            if (event.key !== 'Escape') return;
            event.preventDefault();
            $('guideResetConfirmation').hidden = true;
            $('restoreGeneratedGuide').focus();
        });
        return bridge;
    });
})();
