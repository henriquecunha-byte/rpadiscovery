/* Synthetic browser scenarios only. Ready accounts below are test doubles, not an auth provider. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.QA_BASE_URL || 'http://127.0.0.1:8772';
const output = path.resolve('cache/context-privacy-qa-evidence');
const draftKey = 'btime.discovery.draft.v1';
const folderKey = 'btime.discovery.drive-folder';
const legacy = {title: 'Pedido local existente', process_context: 'Manter literalmente o guia da operação Trevo. Não reescrever.', audience: 'Equipe de RPA', detail_level: 'detalhado', api_budget_usd: 2};
const future = {mode: 'required', provider: 'future-test-double', status: 'ready', enabled: true, can_continue_local: false};
const accountA = {id: 'qa-account-a', email: 'a@example.test'};
const accountB = {id: 'qa-account-b', email: 'b@example.test'};
const results = [];
fs.mkdirSync(output, {recursive: true});
const jobFor = user => ({id: 'analysis-' + user.id, title: 'Material de ' + user.email, status: 'COMPLETED', progress: 100, detail_level: 'operacional', created_at: '2026-10-08T12:00:00Z'});
(async () => {
  const browser = await chromium.launch({headless: true, channel: 'chrome'});
  async function scenario(name, work) {
    const context = await browser.newContext({viewport: {width: 1440, height: 1050}, reducedMotion: 'reduce'});
    const page = await context.newPage();
    page.setDefaultTimeout(8000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    try {
      await work(page, context);
      assert.deepEqual(errors, []);
      results.push({name, status: 'PASS'});
      console.log('PASS ' + name);
    } catch (error) {
      results.push({name, status: 'FAIL', error: error.message, pageErrors: errors});
      console.log('FAIL ' + name + ': ' + error.message);
      await page.screenshot({path: path.join(output, 'failure-' + results.length + '.png'), fullPage: true}).catch(() => {});
    } finally { await context.close(); }
  }
  async function load(page, hash = '#new') {
    await page.goto(base + '/' + hash);
    await page.waitForFunction(() => window.DiscoveryAuth);
    await page.evaluate(() => window.DiscoveryAuth.ready);
    await page.evaluate(() => window.DiscoveryContextForm.ready);
  }
  async function mockAccount(page, getUser) {
    await page.route('**/api/auth/config', route => route.fulfill({json: future}));
    await page.route('**/api/auth/session', route => route.fulfill({json: {authenticated: !!getUser(), user: getUser()}}));
    await page.route('**/api/jobs', route => route.fulfill({json: getUser() ? [jobFor(getUser())] : []}));
    await page.route('**/api/health', route => route.fulfill({json: {status: 'ok', worker: true, ffmpeg: true, ffprobe: true, api_configured: false}}));
    await page.route('**/api/drive/status', route => route.fulfill({json: {configured: false, connected: false}}));
  }
  async function contextStep(page) {
    await page.locator('#videoInput').setInputFiles({name: 'entrevista-sintetica.mp4', mimeType: 'video/mp4', buffer: Buffer.from('synthetic-ui-fixture')});
    await page.locator('#nextStep').click();
    await page.locator('#step2').waitFor({state: 'visible'});
  }
  async function editGuide(page, guide) {
    if (await page.locator('#toggleGuide').getAttribute('aria-expanded') === 'false') await page.locator('#toggleGuide').click();
    if (await page.locator('#editGuide').isVisible()) await page.locator('#editGuide').click();
    await page.locator('#context').fill(guide);
  }
  async function assertEmptyContext(page) {
    assert.equal(await page.locator('#cliente').inputValue(), '');
    assert.equal(await page.locator('#processo').inputValue(), '');
    assert.equal(await page.locator('#publico input:checked').count(), 0);
    const value = await page.evaluate(() => window.DiscoveryContextForm.getValue());
    assert.equal(value.guiaEditado, false);
    assert.equal(value.instrucoesExtras, '');
    assert.deepEqual(value.sistemas, []);
    assert.equal(value.guia, await page.evaluate(() => window.DiscoveryContextModel.compileGuide(window.DiscoveryContextModel.defaultContext())));
  }
  async function seedLegacy(context) {
    await context.addInitScript(({draftKey, folderKey, legacy}) => {
      if (!localStorage.getItem('qa-seeded')) {
        localStorage.setItem(draftKey, JSON.stringify(legacy));
        localStorage.setItem(folderKey, 'legacy-local-folder');
        localStorage.setItem('qa-seeded', '1');
      }
    }, {draftKey, folderKey, legacy});
  }
  try {
    await scenario('Contexto estruturado migra o rascunho local v1 sem reescrever o guia manual', async (page, context) => {
      await seedLegacy(context);
      await load(page);
      await contextStep(page);
      assert.equal(await page.locator('label[for=processo]').innerText(), 'Nome do processo obrigatório');
      assert.equal(await page.locator('#processo').inputValue(), legacy.title);
      assert.equal(await page.locator('#cliente').inputValue(), '');
      assert.equal(await page.locator('#context').inputValue(), legacy.process_context);
      assert.equal(await page.locator('#publico input[value=rpa]').isChecked(), true);
      assert.equal(await page.locator('#etapaDestino input:checked').count(), 0);
      assert.equal(await page.locator('#toggleGuide').getAttribute('aria-expanded'), 'false');
      assert.equal(await page.locator('#audience, #detail').count(), 0);
      const migrated = await page.evaluate(key => JSON.parse(localStorage.getItem(key)), draftKey);
      assert.equal(migrated.version, 2);
      assert.equal(migrated.contexto.guiaEditado, true);
      assert.equal(migrated.contexto.guia, legacy.process_context);
      assert.equal(await page.evaluate(() => window.DiscoveryAuth.accountKey), 'local');
      assert.equal(await page.evaluate(() => window.DiscoveryAuth.canPersistLocal), true);
      assert.match(await page.locator('#workspacePrivacy').innerText(), /Sem separação/);
      await page.locator('#processo').fill('Entrevista sobre experiência do cliente');
      await page.screenshot({path: path.join(output, 'context-desktop.png'), fullPage: true});
      for (const width of [320, 375, 768, 1440]) {
        await page.setViewportSize({width, height: 1000});
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      }
      await page.setViewportSize({width: 375, height: 1000});
      await page.screenshot({path: path.join(output, 'context-mobile.png'), fullPage: true});
      await page.reload();
      await page.evaluate(() => window.DiscoveryAuth.ready);
      await page.evaluate(() => window.DiscoveryContextForm.ready);
      assert.equal(await page.locator('#processo').inputValue(), 'Entrevista sobre experiência do cliente');
      assert.equal(await page.locator('#context').inputValue(), legacy.process_context);
    });
    await scenario('Conta confirmada ignora rascunho e pasta legados; dados da conta não persistem no navegador', async (page, context) => {
      await seedLegacy(context);
      await mockAccount(page, () => accountA);
      await load(page);
      assert.equal(await page.evaluate(() => window.DiscoveryAuth.accountKey), 'user:' + accountA.id);
      assert.equal(await page.evaluate(() => window.DiscoveryAuth.canPersistLocal), false);
      await assertEmptyContext(page);
      assert.equal(await page.locator('#driveFolder').inputValue(), '');
      assert.equal(await page.locator('#workspaceAccessMode').innerText(), 'Conta individual');
      await contextStep(page);
      await page.locator('#cliente').fill('Cliente privado de A');
      await page.locator('#processo').fill('Rascunho privado de A');
      await editGuide(page, 'Este conteúdo existe apenas na sessão da conta A.');
      assert.match(await page.locator('#draftStatus').innerText(), /sessão/);
      await page.evaluate(() => { const input = document.querySelector('#driveFolder'); input.value = 'private-folder-a'; input.dispatchEvent(new Event('input', {bubbles: true})); });
      assert.deepEqual(await page.evaluate(key => JSON.parse(localStorage.getItem(key)), draftKey), legacy);
      assert.equal(await page.evaluate(key => localStorage.getItem(key), folderKey), 'legacy-local-folder');
      assert.equal(await page.evaluate(() => JSON.stringify({...localStorage, ...sessionStorage}).includes('privado de A')), false);
      await page.reload();
      await page.evaluate(() => window.DiscoveryAuth.ready);
      await page.evaluate(() => window.DiscoveryContextForm.ready);
      await assertEmptyContext(page);
      assert.equal(await page.locator('#driveFolder').inputValue(), '');
    });
    await scenario('Mudança A para B com clear=false remove arquivos, campos e resposta antiga da conta A', async page => {
      let user = accountA;
      await mockAccount(page, () => user);
      await load(page);
      await contextStep(page);
      await page.locator('#cliente').fill('Cliente secreto da conta A');
      await page.locator('#processo').fill('Segredo da conta A');
      await editGuide(page, 'Guia particular da conta A.');
      await page.evaluate(() => { location.hash = 'history'; });
      await page.locator('#jobs').filter({hasText: accountA.email}).waitFor();
      let release;
      let holdNext = true;
      const gate = new Promise(resolve => { release = resolve; });
      await page.route('**/api/jobs', async route => {
        const responseUser = user;
        if (holdNext) { holdNext = false; await gate; }
        await route.fulfill({json: [jobFor(responseUser)]}).catch(() => {});
      });
      const requested = page.waitForRequest('**/api/jobs');
      await page.locator('#refresh').click();
      await requested;
      await page.evaluate(() => { window.qaIdentityEvents = []; window.addEventListener('discovery:authchange', event => window.qaIdentityEvents.push(event.detail)); });
      user = accountB;
      await page.evaluate(() => window.dispatchEvent(new Event('focus')));
      await page.waitForFunction(id => window.DiscoveryAuth.accountKey === 'user:' + id, accountB.id);
      await page.locator('#jobs').filter({hasText: accountB.email}).waitFor();
      release();
      await page.waitForTimeout(200);
      await assertEmptyContext(page);
      assert.equal(await page.locator('#fileStack .file-row').count(), 0);
      assert.equal(await page.locator('#jobs').innerText().then(text => text.includes(accountA.email)), false);
      assert.equal(await page.locator('#sessionLabel').innerText(), accountB.email);
      assert.equal(await page.evaluate(() => window.qaIdentityEvents.some(event => event.reason === 'identity' && event.clear === false)), true);
      assert.equal(await page.locator('#previewStack video').count(), 0);
    });
    await scenario('Sessão revogada em outra aba bloqueia o workspace e elimina o material renderizado', async page => {
      let user = accountA;
      await mockAccount(page, () => user);
      await load(page, '#history');
      await page.locator('#jobs').filter({hasText: accountA.email}).waitFor();
      user = null;
      await page.evaluate(() => window.dispatchEvent(new Event('focus')));
      await page.locator('#authView').waitFor({state: 'visible'});
      assert.equal(await page.evaluate(() => window.DiscoveryAuth.accountKey), null);
      assert.equal(await page.evaluate(() => window.DiscoveryAuth.canPersistLocal), false);
      assert.equal(await page.locator('#jobs').innerText().then(text => text.includes(accountA.email)), false);
      assert.equal(await page.locator('#continueLocal').isVisible(), false);
    });
    await scenario('Novo pedido começa sem cliente ou público e revisão apresenta contexto escolhido', async page => {
      await load(page);
      await contextStep(page);
      await assertEmptyContext(page);
      await page.locator('#perfil').selectOption('processo');
      assert.equal(await page.locator('#solucoes input[value=indefinido]').isChecked(), true);
      await page.locator('#cliente').fill('Cliente de QA');
      await page.locator('#processo').fill('Treinamento de comunicação');
      await page.locator('#etapaDestino input[value=desenho]').check();
      await page.locator('#publico input[value=cliente]').check();
      await editGuide(page, 'Organizar os exemplos do treinamento por tema, sem resumir perguntas e respostas.');
      await page.locator('#form').screenshot({path: path.join(output, 'context-general-desktop.png')});
      await page.setViewportSize({width: 375, height: 1000});
      await page.locator('#form').screenshot({path: path.join(output, 'context-general-mobile.png')});
      await page.setViewportSize({width: 1440, height: 1050});
      await page.locator('#nextStep').click();
      await page.locator('#step3').waitFor({state: 'visible'});
      assert.equal(await page.locator('.review-summary .eyebrow').innerText(), 'ANÁLISE');
      assert.equal(await page.locator('#reviewTitle').innerText(), 'Treinamento de comunicação');
      assert.match(await page.locator('#reviewDetail').innerText(), /Resumido · Cliente/);
      assert.match(await page.locator('#reviewStructured').innerText(), /Cliente de QA/);
      assert.match(await page.locator('#reviewStructured').innerText(), /Desenho e validação da solução/);
    });
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify({results}, null, 2));
  }
  console.log(results.filter(result => result.status === 'PASS').length + '/' + results.length + ' passed');
  if (results.some(result => result.status === 'FAIL')) process.exitCode = 1;
})().catch(error => { console.error(error); process.exitCode = 1; });
