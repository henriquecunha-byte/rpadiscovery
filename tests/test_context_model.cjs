'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const model = require('../rpa_docs/static/context-model.js');
const snapshots = require('./fixtures/context_snapshots.json');

test('new requests default to general while old drafts remain process requests', () => {
    assert.equal(model.defaultContext().perfil, 'personalizado');
    assert.equal(model.migrateDraft({version: 2, contexto: snapshots[0].contexto}).contexto.perfil, 'processo');
    for (const profile of Object.keys(model.rules.profiles).filter(key => key !== 'processo')) {
        const context = {...model.defaultContext(), perfil: profile, processo: 'Planejamento', publico:['equipe'], guia:'Manual intacto', guiaEditado:true};
        context.entregaveis = model.suggestDeliverables(context);
        const restored = model.migrateDraft({version:2, contexto:context}).contexto;
        assert.equal(restored.perfil, profile);
        assert.equal(restored.guia, 'Manual intacto');
        assert.deepEqual(restored.entregaveis, context.entregaveis);
    }
});

for (const fixture of snapshots) {
    test('shared compiler snapshot: ' + fixture.name, () => {
        assert.equal(model.compileGuide(fixture.contexto), fixture.guide);
        assert.doesNotMatch(fixture.guide, /\.mp4|\.mov|\.webm|Processo operacional/);
    });
}
test('optional empty values omit complete labels', () => {
    const guide = model.compileGuide({ ...model.defaultContext(), solucoes: [] });
    assert.doesNotMatch(guide, /Cliente:|Processo:|Por que está sendo mapeado:|Sistemas citados:|Instruções adicionais:|Quem vai ler:|Este material alimenta|sobre ""/);
});
test('suggestions use an ordered union and ignore selected input order', () => {
    for (const [stage, base] of Object.entries(model.ENTREGAVEIS_SUGERIDOS.base)) {
        for (const [solution, extra] of Object.entries(model.ENTREGAVEIS_SUGERIDOS.extra)) {
            const expected = Object.keys(model.labels.entregaveis).filter(key => [...base, ...extra].includes(key));
            assert.deepEqual(model.suggestDeliverables({ etapaDestino: stage, solucoes: [solution] }), expected);
        }
    }
    assert.deepEqual(model.suggestDeliverables({ solucoes: ['rpa'] }), []);
});
test('default values are isolated for each new context', () => {
    const left = model.defaultContext(), right = model.defaultContext();
    left.solucoes.push('rpa');
    assert.deepEqual(right.solucoes, ['indefinido']);
    assert.equal(right.etapaDestino, null);
    assert.equal(right.etapaDestinoTocado, false);
});
test('compiler never mutates context or appends recording metadata', () => {
    const context = { ...snapshots[0].contexto, sources: ['private.mp4'] }, before = JSON.stringify(context);
    assert.equal(model.compileGuide(context), snapshots[0].guide);
    assert.equal(JSON.stringify(context), before);
});
test('v1 known audience and operational level migrate with manual guide intact', () => {
    const draft = model.migrateDraft({ title: 'Pedidos', audience: 'Equipe de RPA', detail_level: 'operacional', process_context: 'Somente o trecho solicitado.', api_budget_usd: '2.50' });
    assert.equal(draft.version, 2);
    assert.equal(draft.contexto.cliente, '');
    assert.equal(draft.contexto.processo, 'Pedidos');
    assert.deepEqual(draft.contexto.publico, ['rpa']);
    assert.equal(draft.contexto.etapaDestino, 'doc_tecnica');
    assert.equal(draft.contexto.etapaDestinoTocado, true);
    assert.equal(draft.contexto.guia, 'Somente o trecho solicitado.');
    assert.equal(draft.contexto.guiaEditado, true);
    assert.equal(draft.api_budget_usd, 2.5);
});
test('v1 unknown audience migrates to Outro and other levels require choice', () => {
    for (const detail of ['resumido', 'detalhado', '']) {
        const draft = model.migrateDraft({ version: 1, title: 'Aula', audience: 'Estudantes', detail_level: detail });
        assert.deepEqual(draft.contexto.publico, ['outro']);
        assert.equal(draft.contexto.publicoOutro, 'Estudantes');
        assert.equal(draft.contexto.etapaDestino, null);
        assert.equal(draft.contexto.guiaEditado, false);
    }
});
test('v1 displayed operational label is recognized', () => {
    assert.equal(model.migrateDraft({ title: 'Pedidos', detail_level: 'Operacional — passo a passo' }).contexto.etapaDestino, 'doc_tecnica');
});
test('v2 incomplete draft remains recoverable and generated text is refreshed', () => {
    const draft = model.migrateDraft({ version: 2, contexto: { processo: 'Pedidos', guia: 'STALE' } });
    assert.equal(draft.contexto.cliente, '');
    assert.equal(draft.contexto.etapaDestino, null);
    assert.doesNotMatch(draft.contexto.guia, /STALE/);
    assert.deepEqual(draft.contexto.solucoes, ['indefinido']);
});
test('v2 manually touched fields and guide survive reload', () => {
    const context = { ...model.defaultContext(), ...snapshots[0].contexto, etapaDestinoTocado: true, entregaveisTocado: true, guiaEditado: true, guia: 'Meu guia.' };
    const draft = model.migrateDraft(JSON.stringify({ version: 2, contexto: context, api_budget_usd: 4 }));
    assert.deepEqual(draft.contexto.entregaveis, context.entregaveis);
    assert.equal(draft.contexto.etapaDestinoTocado, true);
    assert.equal(draft.contexto.guia, 'Meu guia.');
});
test('corrupt drafts and unsupported versions are discarded safely', () => {
    for (const value of ['broken json', 'null', null, [], {}, { version: 3 }, { title: {} }, { version: 2, contexto: [] }, { version: 2, contexto: { publico: ['admin'] } }, { version: 2, contexto: { solucoes: ['rpa', 'indefinido'] } }, { version: 2, contexto: { guiaEditado: 'false' } }, { version: 2, contexto: { etapaDestino: '__proto__' } }, { version: 2, contexto: { sistemas: ['Excel', 'excel'] } }, { version: 2, contexto: { cliente: 'a'.repeat(81) } }]) {
        assert.equal(model.migrateDraft(value), null);
    }
});
test('invalid stored budget falls back to a safe reference value', () => {
    for (const budget of [0, -1, 51, 'NaN', Infinity, null]) {
        assert.equal(model.migrateDraft({ title: 'Teste', api_budget_usd: budget }).api_budget_usd, 1);
    }
});
test('manual empty draft is preserved so the UI can show its validation error', () => {
    const draft = model.migrateDraft({ version: 2, contexto: { guiaEditado: true, guia: '' } });
    assert.equal(draft.contexto.guia, '');
    assert.equal(draft.contexto.guiaEditado, true);
});
test('sensitive rule is emitted only when enabled', () => {
    assert.doesNotMatch(model.compileGuide(model.defaultContext()), /\[CPF\]/);
    assert.match(model.compileGuide({ ...model.defaultContext(), dadosSensiveis: true }), /\[CPF\].*\[NOME\]/);
});
test('literal dollar replacement sequences in user process are preserved', () => {
    assert.match(model.compileGuide({ processo: '$& $` $\'' }), /sobre "\$& \$` \$'"/);
});
test('delivery mode defaults to documents only for new requests, not historical drafts', () => {
    assert.equal(model.defaultContext().modoEntrega, 'documentacao');
    assert.equal(model.migrateDraft({title:'Legado'}).contexto.modoEntrega, 'documentacao_previews');
    assert.equal(model.migrateDraft({version:2,contexto:{perfil:'reuniao'}}).contexto.modoEntrega, 'documentacao_previews');
});
test('delivery mode is preserved through valid draft migrations', () => {
    for(const modoEntrega of ['documentacao','documentacao_previews'])
        assert.equal(model.migrateDraft({version:2,contexto:{perfil:'reuniao',modoEntrega}}).contexto.modoEntrega,modoEntrega);
});
