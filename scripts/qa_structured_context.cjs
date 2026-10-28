/* Isolated structured-context browser checks. No real AI, uploads, or queue edits. */
'use strict';
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.QA_BASE_URL || 'http://127.0.0.1:8772';
const output = path.resolve('cache', 'context-qa-evidence');
fs.mkdirSync(output, { recursive: true });
const results = [], pageErrors = [], unexpectedWrites = [], dialogs = [];
let browser, browserContext, page;
const selector = (name, value) => 'input[name="' + name + '"][value="' + value + '"]';
const checked = async name => page.locator('input[name="' + name + '"]:checked').evaluateAll(inputs => inputs.map(input => input.value));
const contextValue = () => page.evaluate(() => window.DiscoveryContextForm.getValue());
async function fresh(options = {}) {
    if (browserContext) await browserContext.close();
    browserContext = await browser.newContext({ viewport: { width: options.width || 1440, height: 1080 }, reducedMotion: 'reduce' });
    await browserContext.route('**/api/**', async route => {
        const request = route.request();
        if (request.method() === 'GET') return route.continue();
        unexpectedWrites.push(request.method() + ' ' + request.url());
        return route.abort('blockedbyclient');
    });
    page = await browserContext.newPage();
    page.setDefaultTimeout(10000);
    page.on('pageerror', error => pageErrors.push(error.message));
    page.on('dialog', async dialog => { dialogs.push(dialog.type()); await dialog.dismiss(); });
    await page.route('**/api/jobs', route => route.fulfill({ json: [] }));
    if (options.draft !== undefined) await page.addInitScript(raw => localStorage.setItem('btime.discovery.draft.v1', raw), typeof options.draft === 'string' ? options.draft : JSON.stringify(options.draft));
    await page.goto(base + '/#new');
    await page.waitForFunction(() => window.DiscoveryContextForm?.getValue().solucoes && document.querySelector('#healthLabel')?.textContent !== 'Conectando…');
    await page.locator('#videoInput').setInputFiles([
        { name: 'contexto-qa-a.mp4', mimeType: 'video/mp4', buffer: Buffer.from('synthetic-a-no-processing') },
        { name: 'contexto-qa-b.webm', mimeType: 'video/webm', buffer: Buffer.from('synthetic-b-no-processing') },
    ]);
    await page.locator('#nextStep').click();
    await page.locator('#step2').waitFor({ state: 'visible' });
    // This legacy regression suite exercises the original process profile.
    await page.locator('#perfil').selectOption('processo');
}
async function basic() {
    await page.locator('#cliente').fill('Cliente sintético');
    await page.locator('#processo').fill('Gestão de pedidos');
}
async function complete() {
    await basic();
    await page.locator(selector('solucoes', 'rpa')).check();
    await page.locator(selector('publico', 'rpa')).check();
}
async function openGuide() { if (await page.locator('#guidePanel').isHidden()) await page.locator('#toggleGuide').click(); }
async function check(name, work) {
    try { await work(); results.push({ name, status: 'PASS' }); console.log('PASS ' + name); }
    catch (error) {
        results.push({ name, status: 'FAIL', error: error.stack }); console.log('FAIL ' + name + ': ' + error.message);
        if (page && !page.isClosed()) await page.screenshot({ path: path.join(output, 'failure-' + results.length + '.png'), fullPage: true }).catch(() => {});
    }
}
(async () => {
    browser = await chromium.launch({ headless: true, channel: 'chrome' });
    await check('Defaults: undefined solution, no stage and collapsed guide', async () => {
        await fresh();
        assert.deepEqual(await checked('solucoes'), ['indefinido']);
        assert.deepEqual(await checked('etapaDestino'), []);
        assert.equal(await page.locator('#entregaveisChoices').isHidden(), true);
        assert.equal(await page.locator('#guidePanel').isHidden(), true);
        assert.equal(await page.locator('#toggleGuide').getAttribute('aria-expanded'), 'false');
        assert.equal(await page.locator('#suggestPrompt').isDisabled(), true);
        assert.equal(await page.locator('#nextStep').isEnabled(), true);
    });
    await check('Continue validates and focuses first field, not on initial typing', async () => {
        await fresh();
        await page.locator('#cliente').focus();
        await page.keyboard.type('C');
        assert.equal(await page.locator('#clienteError').innerText(), '');
        await page.locator('#cliente').fill('');
        await page.locator('#nextStep').click();
        assert.equal(await page.evaluate(() => document.activeElement.id), 'cliente');
        assert.equal(await page.locator('#clienteError').innerText(), 'Informe o cliente.');
        assert.equal(await page.locator('#cliente').getAttribute('aria-invalid'), 'true');
        assert.equal(await page.locator('#step2').isVisible(), true);
        await page.locator('#cliente').fill('Cliente');
        await page.locator('#processo').focus();
        assert.equal(await page.locator('#cliente').getAttribute('aria-invalid'), null);
    });
    await check('RPA auto-selects its stage until a manual stage choice', async () => {
        await fresh();
        await page.locator(selector('solucoes', 'rpa')).check();
        assert.deepEqual(await checked('solucoes'), ['rpa']);
        assert.deepEqual(await checked('etapaDestino'), ['spec_rpa']);
        assert.equal((await contextValue()).etapaDestinoTocado, false);
        await page.locator(selector('etapaDestino', 'desenho')).check();
        await page.locator(selector('solucoes', 'indefinido')).check();
        await page.locator(selector('solucoes', 'rpa')).check();
        assert.deepEqual(await checked('etapaDestino'), ['desenho']);
        assert.equal((await contextValue()).etapaDestinoTocado, true);
    });
    await check('Undefined solution is exclusive; specific solutions combine', async () => {
        await fresh();
        await page.locator(selector('solucoes', 'ia')).check();
        await page.locator(selector('solucoes', 'integracao')).check();
        assert.deepEqual(await checked('solucoes'), ['ia', 'integracao']);
        await page.locator(selector('solucoes', 'indefinido')).check();
        assert.deepEqual(await checked('solucoes'), ['indefinido']);
        await page.locator(selector('solucoes', 'indefinido')).uncheck();
        await page.locator('#nextStep').click();
        assert.match(await page.locator('#solucoesError').innerText(), /ao menos uma/);
        assert.equal(await page.locator('#solucoes').getAttribute('aria-invalid'), 'true');
        await page.locator(selector('solucoes', 'ia')).check();
        assert.equal(await page.locator('#solucoesError').innerText(), '');
        assert.equal(await page.locator('#solucoes').getAttribute('aria-invalid'), null);
    });
    await check('Deliverable suggestions update until touched, then reset explicitly', async () => {
        await fresh();
        await page.locator(selector('etapaDestino', 'desenho')).check();
        assert.deepEqual(await checked('entregaveis'), ['fluxo_atual', 'sistemas_telas', 'volume_tempo', 'dores', 'oportunidades', 'perguntas_abertas']);
        await page.locator(selector('solucoes', 'ia')).check();
        assert.ok((await checked('entregaveis')).includes('regras_excecoes'));
        await page.locator(selector('entregaveis', 'fluxo_atual')).uncheck();
        const chosen = await checked('entregaveis');
        await page.locator(selector('etapaDestino', 'spec_rpa')).check();
        assert.deepEqual(await checked('entregaveis'), chosen);
        assert.equal(await page.locator('#resetDeliverables').isVisible(), true);
        await page.locator('#resetDeliverables').click();
        assert.deepEqual(await checked('entregaveis'), ['fluxo_atual', 'sistemas_telas', 'campos_io', 'regras_excecoes', 'prints_por_tela', 'perguntas_abertas']);
        assert.equal((await contextValue()).entregaveisTocado, false);
    });
    await check('Multiple audiences and conditional Other require its label', async () => {
        await fresh(); await complete();
        await page.locator(selector('publico', 'cliente')).check();
        await page.locator(selector('publico', 'outro')).check();
        assert.equal(await page.locator('#publicoOutro').isVisible(), true);
        await page.locator('#nextStep').click();
        assert.equal(await page.evaluate(() => document.activeElement.id), 'publicoOutro');
        assert.equal(await page.locator('#publicoOutroError').innerText(), 'Diga quem é o público.');
        await page.locator('#publicoOutro').fill('Operações');
        await openGuide();
        assert.match(await page.locator('#context').inputValue(), /Equipe de RPA, Cliente \(validação\), Operações/);
        await page.locator(selector('publico', 'outro')).uncheck();
        assert.equal(await page.locator('#publicoOutroField').isHidden(), true);
    });
    await check('Tags support comma, Enter, duplicate detection and Backspace', async () => {
        await fresh();
        await page.locator('#sistemas').fill('Excel,WhatsApp,');
        assert.deepEqual((await contextValue()).sistemas, ['Excel', 'WhatsApp']);
        await page.locator('#sistemas').fill('excel');
        await page.locator('#sistemas').press('Enter');
        assert.equal((await contextValue()).sistemas.length, 2);
        await page.locator('#sistemas').press('Backspace');
        assert.deepEqual((await contextValue()).sistemas, ['Excel']);
        await page.locator('#sistemas').fill('SAP');
        await page.locator('#sistemas').press('Enter');
        await page.getByRole('button', { name: 'Remover Excel', exact: true }).click();
        assert.deepEqual((await contextValue()).sistemas, ['SAP']);
    });
    await check('Tags cap at 15 without silently losing the overflow text', async () => {
        await fresh();
        for (let index = 1; index <= 16; index++) {
            await page.locator('#sistemas').fill('Sistema ' + index);
            await page.locator('#sistemas').press('Enter');
        }
        assert.equal((await contextValue()).sistemas.length, 15);
        assert.equal(await page.locator('#sistemas').inputValue(), 'Sistema 16');
        assert.match(await page.locator('#sistemasStatus').innerText(), /até 15/);
    });
    await check('Generated guide refreshes and does not include recording filenames', async () => {
        await fresh(); await complete(); await openGuide();
        assert.equal(await page.locator('#context').getAttribute('readonly'), '');
        await page.locator('#objetivo').fill('Reduzir a cópia manual.');
        await page.locator('#instrucoesExtras').fill('O pedido também é chamado de OS.');
        const guide = await page.locator('#context').inputValue();
        assert.match(guide, /Reduzir a cópia manual/);
        assert.match(guide, /Instruções adicionais:\nO pedido também é chamado de OS\./);
        assert.doesNotMatch(guide, /contexto-qa|\.mp4|\.webm|Processo operacional/);
    });
    await check('Manual guide stays locked; returning to generated guide uses inline confirmation', async () => {
        await fresh(); await complete(); await openGuide();
        await page.locator('#editGuide').click();
        await page.locator('#context').fill('Meu guia manual.');
        await page.locator('#processo').fill('Processo atualizado');
        assert.equal(await page.locator('#context').inputValue(), 'Meu guia manual.');
        await page.locator('#restoreGeneratedGuide').click();
        assert.equal(await page.locator('#guideResetConfirmation').isVisible(), true);
        await page.locator('#cancelGuideReset').click();
        assert.equal(await page.locator('#context').inputValue(), 'Meu guia manual.');
        await page.locator('#restoreGeneratedGuide').click();
        await page.locator('#confirmGuideReset').click();
        assert.match(await page.locator('#context').inputValue(), /Processo: Processo atualizado/);
        assert.equal((await contextValue()).guiaEditado, false);
        assert.deepEqual(dialogs, []);
    });
    await check('Empty manual guide blocks Review and focuses the expanded guide', async () => {
        await fresh(); await complete(); await openGuide();
        await page.locator('#editGuide').click();
        await page.locator('#context').fill('');
        await page.locator('#toggleGuide').click();
        await page.locator('#nextStep').click();
        assert.equal(await page.evaluate(() => document.activeElement.id), 'context');
        assert.equal(await page.locator('#guidePanel').isVisible(), true);
        assert.equal(await page.locator('#contextError').innerText(), 'O guia não pode ficar vazio.');
    });
    await check('Sensitive option adds instructions and clearly does not promise redaction', async () => {
        await fresh(); await complete();
        await page.locator('#dadosSensiveis').check();
        assert.equal(await page.locator('#dadosSensiveis').getAttribute('aria-checked'), 'true');
        assert.match(await page.locator('#dadosSensiveisHelp').innerText(), /não são anonimizados automaticamente/);
        assert.match((await contextValue()).guia, /\[CPF\].*\[NOME\]/);
        await page.locator('#nextStep').click();
        assert.equal(await page.locator('#reviewSensitive').isVisible(), true);
        assert.match(await page.locator('#reviewSensitive').innerText(), /não são anonimizados automaticamente/);
    });
    await check('Review shows structured metadata for two synthetic recordings', async () => {
        await fresh(); await complete();
        await page.locator('#nextStep').click();
        assert.equal(await page.locator('#step3').isVisible(), true);
        const summary = await page.locator('#reviewStructured').innerText();
        for (const text of ['Cliente sintético', 'Gestão de pedidos', 'RPA', 'Especificação de RPA', 'Equipe de RPA', 'Print de cada tela com descrição']) assert.ok(summary.includes(text), text);
        assert.match(await page.locator('#reviewSources').innerText(), /2 arquivo/);
    });
    await check('AI mock success receives context but no source names and marks guide edited', async () => {
        await fresh(); await basic(); await openGuide();
        let payload;
        await page.route('**/api/prompt/suggest', route => { payload = route.request().postDataJSON(); return route.fulfill({ json: { ok: true, prompt: 'Guia melhorado sintético: preserve perguntas, respostas e todas as regras de evidência.', generated: true } }); });
        await page.locator('#suggestPrompt').click();
        await page.waitForFunction(() => window.DiscoveryContextForm.getValue().guiaEditado);
        assert.equal(payload.contexto.cliente, 'Cliente sintético');
        assert.equal(payload.contexto.etapaDestino, null);
        assert.equal(Object.hasOwn(payload, 'sources'), false);
        assert.doesNotMatch(JSON.stringify(payload), /contexto-qa-a|contexto-qa-b|\.mp4|\.webm/);
        assert.match(await page.locator('#context').inputValue(), /Guia melhorado sintético/);
    });
    await check('Provider 401 envelope is neutral, preserves generated guide and exposes no key', async () => {
        await fresh(); await basic(); await openGuide();
        const before = await page.locator('#context').inputValue();
        await page.route('**/api/prompt/suggest', route => route.fulfill({ json: { ok: false, code: 'ai_unavailable' } }));
        await page.locator('#suggestPrompt').click();
        await page.waitForFunction(() => document.querySelector('#promptHint').textContent.startsWith('Não conseguimos'));
        assert.equal(await page.locator('#promptHint').innerText(), 'Não conseguimos melhorar o guia com IA agora. O guia gerado pelos campos continua valendo.');
        assert.equal(await page.locator('#promptHint').getAttribute('aria-live'), 'polite');
        assert.equal(await page.locator('#context').inputValue(), before);
        assert.equal((await contextValue()).guiaEditado, false);
        assert.doesNotMatch(await page.locator('body').innerText(), /sk-proj|Incorrect API key|Error code: 401/);
    });
    await check('Late AI result asks before overwriting a changed request', async () => {
        await fresh(); await basic(); await openGuide();
        let release, received;
        const blocked = new Promise(resolve => { release = resolve; });
        const requested = new Promise(resolve => { received = resolve; });
        await page.route('**/api/prompt/suggest', async route => { received(); await blocked; await route.fulfill({ json: { ok: true, prompt: 'Resposta atrasada sintética.' } }); });
        await page.locator('#suggestPrompt').click(); await requested;
        await page.locator('#objetivo').fill('Objetivo editado durante a solicitação.');
        release();
        await page.locator('#confirmDialog').waitFor({ state: 'visible' });
        assert.match(await page.locator('#confirmTitle').innerText(), /Aplicar a sugestão/);
        await page.locator('#rejectConfirm').click();
        assert.match(await page.locator('#context').inputValue(), /Objetivo editado durante/);
        assert.doesNotMatch(await page.locator('#context').inputValue(), /Resposta atrasada/);
    });
    await check('Legacy local draft migrates without losing guide or inventing a client', async () => {
        await fresh({ draft: { title: 'Processo anterior', process_context: 'Meu guia anterior permanece.', audience: 'Equipe de RPA', detail_level: 'operacional', api_budget_usd: 2 } });
        assert.equal(await page.locator('#cliente').inputValue(), '');
        assert.equal(await page.locator('#processo').inputValue(), 'Processo anterior');
        assert.deepEqual(await checked('publico'), ['rpa']);
        assert.deepEqual(await checked('etapaDestino'), ['doc_tecnica']);
        assert.equal((await contextValue()).guia, 'Meu guia anterior permanece.');
        assert.equal((await contextValue()).guiaEditado, true);
        assert.equal(await page.locator('#budget').inputValue(), '2');
    });
    await check('Corrupt local draft opens cleanly with safe defaults', async () => {
        await fresh({ draft: '{corrupt-json' });
        assert.equal(await page.locator('#cliente').inputValue(), '');
        assert.equal(await page.locator('#processo').inputValue(), '');
        assert.deepEqual(await checked('solucoes'), ['indefinido']);
        assert.equal((await contextValue()).guiaEditado, false);
    });
    await check('Context persists as v2 with manual choices after reload', async () => {
        await fresh(); await complete();
        await page.locator(selector('etapaDestino', 'doc_tecnica')).check();
        await page.locator(selector('entregaveis', 'volume_tempo')).uncheck();
        await openGuide(); await page.locator('#editGuide').click(); await page.locator('#context').fill('Guia manual persistido.');
        const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('btime.discovery.draft.v1')));
        assert.equal(saved.version, 2);
        assert.equal(saved.contexto.entregaveisTocado, true);
        await page.reload();
        await page.waitForFunction(() => window.DiscoveryContextForm?.getValue().processo === 'Gestão de pedidos');
        const loaded = await contextValue();
        assert.equal(loaded.guia, 'Guia manual persistido.');
        assert.equal(loaded.etapaDestinoTocado, true);
        assert.equal(loaded.entregaveisTocado, true);
        assert.equal(await page.locator('#fileStack .file-stack-item').count(), 0);
    });
    await check('Reusing a job without draft version preserves the full structured context', async () => {
        await fresh(); await complete();
        const saved = { ...(await contextValue()), cliente: 'Cliente do pedido salvo', processo: 'Fluxo salvo', etapaDestino: 'doc_tecnica', etapaDestinoTocado: true, entregaveis: ['regras_excecoes'], entregaveisTocado: true, publico: ['outro'], publicoOutro: 'Operações', guiaEditado: true, guia: 'Guia personalizado do pedido salvo.' };
        const job = { id: 'qa-structured-reuse', title: 'Fluxo salvo', contexto: saved, process_context: saved.guia, audience: 'Operações', detail_level: 'operacional', status: 'FAILED', progress: 0, stage: 'Teste simulado', created_at: '2026-10-08T12:00:00Z', api_budget_usd: 3, api_approved: true, can_retry: false, result: {}, events: [] };
        assert.equal(Object.hasOwn(job, 'version'), false);
        await page.route('**/api/jobs/qa-structured-reuse', route => route.fulfill({ json: job }));
        await page.goto(base + '/#job=qa-structured-reuse');
        await page.locator('#reuseRequest').waitFor({ state: 'visible' });
        await page.waitForFunction(() => !document.querySelector('#reuseRequest').disabled);
        await page.locator('#reuseRequest').click();
        await page.locator('#confirmDialog').waitFor({ state: 'visible' });
        await page.locator('#acceptConfirm').click();
        await page.waitForURL(/#new$/);
        const copied = await contextValue();
        assert.deepEqual(copied, saved);
        assert.equal(await page.locator('#budget').inputValue(), '3');
        assert.equal(await page.locator('#approved').isChecked(), false);
        assert.equal(await page.locator('#fileStack .file-stack-item').count(), 0);
    });
    await check('One-character project names and an Other audience remain valid', async () => {
        await fresh();
        await page.locator('#cliente').fill('A');
        await page.locator('#processo').fill('X');
        await page.locator(selector('solucoes', 'rpa')).check();
        await page.locator(selector('publico', 'outro')).check();
        await page.locator('#publicoOutro').fill('Operações');
        await page.locator('#nextStep').click();
        assert.equal(await page.locator('#step3').isVisible(), true);
        assert.equal(await page.locator('#reviewTitle').innerText(), 'X');
        assert.match(await page.locator('#reviewStructured').innerText(), /Operações/);
    });
    await check('Upload multipart carries structured JSON and matching legacy guide', async () => {
        await fresh(); await complete(); await page.locator('#nextStep').click();
        let payload;
        await page.route('**/api/jobs/upload', route => { payload = route.request().postDataBuffer().toString('utf8'); return route.fulfill({ status: 422, json: { detail: 'Envio interceptado pelo QA; nenhum trabalho criado.' } }); });
        await page.locator('#approved').check();
        await page.locator('#submitJob').click();
        await page.waitForFunction(() => document.querySelector('#error').textContent.includes('interceptado pelo QA'));
        const match = payload.match(/name="contexto"\r\n\r\n([\s\S]*?)\r\n--/);
        assert.ok(match, 'Missing JSON context multipart field');
        const sent = JSON.parse(match[1]);
        assert.equal(sent.cliente, 'Cliente sintético');
        assert.equal(sent.etapaDestino, 'spec_rpa');
        const legacy = payload.match(/name="process_context"\r\n\r\n([\s\S]*?)\r\n--/);
        assert.equal(legacy[1], sent.guia.replace(/\n/g, '\r\n'));
        assert.equal((payload.match(/name="files"/g) || []).length, 2);
        assert.equal(await page.locator('#fileStack .file-stack-item').count(), 2);
    });
    await check('Keyboard chips, radio arrows and accessible guide controls work', async () => {
        await fresh();
        await page.locator(selector('solucoes', 'ia')).focus(); await page.keyboard.press('Space');
        assert.deepEqual(await checked('solucoes'), ['ia']);
        await page.locator(selector('etapaDestino', 'desenho')).focus(); await page.keyboard.press('ArrowRight');
        assert.deepEqual(await checked('etapaDestino'), ['doc_tecnica']);
        await page.locator('#toggleGuide').focus(); await page.keyboard.press('Enter');
        assert.equal(await page.locator('#toggleGuide').getAttribute('aria-expanded'), 'true');
        await page.keyboard.press('Tab');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'instrucoesExtras');
        const outline = await page.locator('#instrucoesExtras').evaluate(element => getComputedStyle(element).outlineStyle);
        assert.notEqual(outline, 'none');
    });
    await check('1440 and 375 layouts have no horizontal overflow', async () => {
        await fresh(); await complete();
        await page.locator('#objetivo').fill('Entender o fluxo atual, suas regras e exceções.');
        await page.locator('#sistemas').fill('Excel,WhatsApp,');
        for (const width of [1440, 375]) {
            await page.setViewportSize({ width, height: 1080 });
            await page.evaluate(() => document.fonts.ready);
            await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
            const metrics = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
            assert.ok(metrics.scroll <= metrics.width + 1, JSON.stringify(metrics));
            await page.screenshot({ path: path.join(output, 'structured-context-' + width + '.png'), fullPage: true });
        }
        await openGuide();
        await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
        const metrics = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
        assert.ok(metrics.scroll <= metrics.width + 1, JSON.stringify(metrics));
        await page.screenshot({ path: path.join(output, 'structured-context-guide-375.png'), fullPage: true });
    });
    await check('No uncaught errors, native confirmations, or unmocked writes', async () => {
        assert.deepEqual(pageErrors, []);
        assert.deepEqual(dialogs, []);
        assert.deepEqual(unexpectedWrites, []);
    });
})().catch(error => { results.push({ name: 'Suite setup', status: 'FAIL', error: error.stack }); console.error(error); }).finally(async () => {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({ base, synthetic: true, noExternalAI: true, results, pageErrors, unexpectedWrites }, null, 2));
    const failed = results.filter(result => result.status === 'FAIL').length;
    console.log(JSON.stringify({ passed: results.length - failed, failed, output }));
    if (failed) process.exitCode = 1;
});
