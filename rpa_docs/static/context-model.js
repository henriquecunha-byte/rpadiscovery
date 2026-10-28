/* Pure context rules; the same JSON and snapshots are consumed by Python. */
(function (root, factory) {
    'use strict';
    if (typeof module === 'object' && module.exports) {
        module.exports = factory(require('./context-rules.json'));
        module.exports.ready = Promise.resolve(module.exports);
    } else {
        const bridge = { ready: null };
        root.DiscoveryContextModel = bridge;
        bridge.ready = fetch('/static/context-rules.json', { cache: 'no-cache' }).then(response => {
            if (!response.ok) throw new Error('Não foi possível carregar as regras do contexto. Atualize a página.');
            return response.json();
        }).then(rules => { Object.assign(bridge, factory(rules)); return bridge; });
    }
})(typeof window === 'undefined' ? globalThis : window, function (rules) {
    'use strict';
    const labels = rules.labels;
    const text = value => typeof value === 'string' ? value.trim() : '';
    const ordered = (values, group) => Object.keys(labels[group]).filter(key => (values || []).includes(key));
    const defaults = {
        perfil: 'personalizado', detalhamento: 'operacional', modoEntrega: 'documentacao',
        cliente: '', processo: '', objetivo: '', solucoes: ['indefinido'], etapaDestino: null,
        etapaDestinoTocado: false, publico: [], publicoOutro: '', entregaveis: [],
        entregaveisTocado: false, sistemas: [], dadosSensiveis: false, instrucoesExtras: '', guia: '', guiaEditado: false,
    };
    function defaultContext() { const value = JSON.parse(JSON.stringify(defaults)); value.entregaveis = suggestDeliverables(value); return value; }
    const isGeneral = context => (context.perfil || 'processo') !== 'processo';
    function compileGeneralGuide(context) {
        const profile = rules.profiles[context.perfil];
        const lines = ['Perfil: ' + profile.label, profile.focus];
        [['processo', 'Assunto'], ['cliente', 'Área ou projeto'], ['objetivo', 'Objetivo']].forEach(([key, label]) => {
            if (text(context[key])) lines.push(label + ': ' + text(context[key]));
        });
        if (audienceLabel(context)) lines.push('Quem vai ler: ' + audienceLabel(context) + '.');
        lines.push('Detalhamento: ' + ({resumido:'Sintético', operacional:'Equilibrado', detalhado:'Detalhado'}[context.detalhamento || 'operacional']) + '.');
        const blocks = [lines.join('\n')], items = ordered(context.entregaveis, 'entregaveis');
        if (items.length) blocks.push('O que a análise precisa entregar:\n' + items.map(key => '- ' + labels.entregaveis[key]).join('\n'));
        if (context.sistemas?.length) blocks.push('Termos e ferramentas de referência: ' + context.sistemas.join(', ') + '.');
        const cuts = ['Regras de corte:'];
        if (text(context.processo)) cuts.push(rules.cutKeep.replace('{processo}', () => text(context.processo)));
        cuts.push(rules.cutDiscard); blocks.push(cuts.join('\n'));
        const evidence = ['Regras de evidência:', ...rules.generalEvidence];
        if (context.dadosSensiveis === true) evidence.push(rules.REGRA_DADOS_SENSIVEIS);
        blocks.push(evidence.join('\n'));
        if (text(context.instrucoesExtras)) blocks.push('Instruções adicionais:\n' + text(context.instrucoesExtras));
        return blocks.join('\n\n');
    }
    function audienceLabel(context) {
        return ordered(context.publico, 'publico').map(key => key === 'outro' ? text(context.publicoOutro) : labels.publico[key]).filter(Boolean).join(', ');
    }
    function suggestDeliverables(context) {
        if (isGeneral(context)) return ordered(rules.profiles[context.perfil].suggestions, 'entregaveis');
        const base = rules.suggestions.base[context.etapaDestino];
        if (!base) return [];
        const wanted = new Set(base);
        (context.solucoes || []).forEach(key => (rules.suggestions.extra[key] || []).forEach(item => wanted.add(item)));
        return Object.keys(labels.entregaveis).filter(key => wanted.has(key));
    }
    function compileGuide(context) {
        if (isGeneral(context)) return compileGeneralGuide(context);
        const blocks = [], project = [];
        [['cliente', 'Cliente'], ['processo', 'Processo'], ['objetivo', 'Por que está sendo mapeado']].forEach(([key, label]) => {
            if (text(context[key])) project.push(label + ': ' + text(context[key]));
        });
        if (project.length) blocks.push(project.join('\n'));
        const stage = context.etapaDestino, destination = [], solutions = ordered(context.solucoes, 'solucoes');
        if (labels.etapas[stage]) destination.push('Este material alimenta a etapa "' + labels.etapas[stage] + '" de um projeto da btime.');
        if (solutions.length) destination.push('Solução em vista: ' + solutions.map(key => labels.solucoes[key]).join(', ') + '.');
        const audience = audienceLabel(context);
        if (audience) destination.push('Quem vai ler: ' + audience + '.');
        if (rules.TOM[stage]) destination.push(rules.TOM[stage]);
        if (destination.length) blocks.push(destination.join('\n'));
        const deliverables = ordered(context.entregaveis, 'entregaveis');
        if (deliverables.length) blocks.push('O que a análise precisa entregar:\n' + deliverables.map(key => '- ' + labels.entregaveis[key]).join('\n'));
        solutions.forEach(key => blocks.push(rules.FOCO[key]));
        const systems = (context.sistemas || []).map(text).filter(Boolean);
        if (systems.length) blocks.push('Sistemas citados: ' + systems.join(', ') + '.');
        const cuts = ['Regras de corte:'];
        if (text(context.processo)) cuts.push(rules.cutKeep.replace('{processo}', () => text(context.processo)));
        cuts.push(rules.cutDiscard);
        blocks.push(cuts.join('\n'));
        const evidence = ['Regras de evidência:', ...rules.evidence];
        if (context.dadosSensiveis === true) evidence.push(rules.REGRA_DADOS_SENSIVEIS);
        blocks.push(evidence.join('\n'));
        if (text(context.instrucoesExtras)) blocks.push('Instruções adicionais:\n' + text(context.instrucoesExtras));
        return blocks.join('\n\n');
    }
    function budget(value) { const number = Number(value); return Number.isFinite(number) && number >= 0.1 && number <= 50 ? number : 1; }
    function validStoredContext(value) {
        if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
        const next = defaultContext();
        if (value.perfil !== undefined && !Object.hasOwn(rules.profiles, value.perfil)) return null;
        next.perfil = value.perfil || 'processo';
        if (value.modoEntrega !== undefined && !['documentacao','documentacao_previews'].includes(value.modoEntrega)) return null;
        next.modoEntrega = value.modoEntrega || 'documentacao_previews';
        if (value.detalhamento !== undefined && !['resumido', 'operacional', 'detalhado'].includes(value.detalhamento)) return null;
        next.detalhamento = value.detalhamento || 'operacional';
        next.entregaveis = [];
        const limits = { cliente: 80, processo: 100, objetivo: 400, publicoOutro: 60, instrucoesExtras: 1500, guia: 8000 };
        for (const [key, limit] of Object.entries(limits)) {
            if (value[key] !== undefined && (typeof value[key] !== 'string' || value[key].length > limit)) return null;
            if (value[key] !== undefined) next[key] = value[key].trim();
        }
        for (const key of ['etapaDestinoTocado', 'entregaveisTocado', 'dadosSensiveis', 'guiaEditado']) {
            if (value[key] !== undefined && typeof value[key] !== 'boolean') return null;
            if (value[key] !== undefined) next[key] = value[key];
        }
        if (value.etapaDestino !== undefined && value.etapaDestino !== null && !Object.hasOwn(labels.etapas, value.etapaDestino)) return null;
        next.etapaDestino = value.etapaDestino || null;
        for (const key of ['solucoes', 'publico', 'entregaveis']) {
            if (value[key] === undefined) continue;
            if (!Array.isArray(value[key]) || value[key].some(item => typeof item !== 'string' || !Object.hasOwn(labels[key], item)) || new Set(value[key]).size !== value[key].length) return null;
            next[key] = [...value[key]];
        }
        if (next.solucoes.includes('indefinido') && next.solucoes.length > 1) return null;
        if (value.sistemas !== undefined) {
            if (!Array.isArray(value.sistemas) || value.sistemas.length > 15 || value.sistemas.some(item => typeof item !== 'string' || !item.trim() || item.trim().length > 80)) return null;
            next.sistemas = value.sistemas.map(item => item.trim());
            if (new Set(next.sistemas.map(item => item.toLocaleLowerCase('pt-BR'))).size !== next.sistemas.length) return null;
        }
        if (!next.entregaveisTocado) next.entregaveis = suggestDeliverables(next);
        if (!next.guiaEditado) next.guia = compileGuide(next);
        return next.guia.length <= 8000 ? next : null;
    }
    function migrateDraft(value) {
        if (typeof value === 'string') { try { value = JSON.parse(value); } catch (_) { return null; } }
        if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
        if (value.version === 2) {
            const contexto = validStoredContext(value.contexto);
            return contexto ? { version: 2, contexto, api_budget_usd: budget(value.api_budget_usd) } : null;
        }
        if (value.version !== undefined && value.version !== 1) return null;
        const oldFields = ['title', 'process_context', 'audience', 'detail_level'];
        if (!oldFields.some(key => Object.hasOwn(value, key)) || oldFields.some(key => value[key] !== undefined && typeof value[key] !== 'string')) return null;
        const context = defaultContext();
        context.perfil = 'processo';
        context.modoEntrega = 'documentacao_previews';
        context.processo = text(value.title).slice(0, 100);
        const audience = text(value.audience);
        if (audience) {
            const match = Object.keys(labels.publico).find(key => labels.publico[key].toLocaleLowerCase('pt-BR') === audience.toLocaleLowerCase('pt-BR'));
            context.publico = [match || 'outro'];
            if (!match || match === 'outro') context.publicoOutro = audience.slice(0, 60);
        }
        if (['operacional', 'Operacional — passo a passo'].includes(value.detail_level)) {
            context.etapaDestino = 'doc_tecnica';
            context.etapaDestinoTocado = true;
        }
        context.entregaveis = suggestDeliverables(context);
        context.guia = text(value.process_context).slice(0, 8000);
        context.guiaEditado = Boolean(context.guia);
        if (!context.guiaEditado) context.guia = compileGuide(context);
        return { version: 2, contexto: context, api_budget_usd: budget(value.api_budget_usd) };
    }
    return { rules, labels, TOM: rules.TOM, FOCO: rules.FOCO, ENTREGAVEIS_SUGERIDOS: rules.suggestions,
        defaultContext, compileGuide, suggestDeliverables, migrateDraft, audienceLabel, isGeneral };
});
