/* Product QA for multiple areas. Synthetic server only; AI is never called. */
'use strict';
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const rules = require('../rpa_docs/static/context-rules.json');
const base = 'http://127.0.0.1:8772';
const output = path.resolve('cache', 'profiles-qa-evidence');
fs.mkdirSync(output, {recursive:true});
const results = [], errors = [];
let browser, context, page;
async function check(name, fn) {
    try { await fn(); results.push({name,status:'PASS'}); console.log('PASS ' + name); }
    catch(error) { results.push({name,status:'FAIL',error:error.message}); console.log('FAIL '+name+': '+error.message); await page?.screenshot({path:path.join(output,'failure-'+results.length+'.png'),fullPage:true}).catch(()=>{}); }
}
async function fresh(draft) {
    await context?.close();
    context = await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
    page = await context.newPage(); page.setDefaultTimeout(10000);
    page.on('pageerror',error=>errors.push(error.message));
    if(draft) await page.addInitScript(draft=>localStorage.setItem('btime.discovery.draft.v1', JSON.stringify(draft)),draft);
    await page.goto(base+'/#new');
    await page.waitForFunction(()=>window.DiscoveryContextForm?.getValue().perfil);
    await page.locator('#videoInput').setInputFiles({name:'comunicacao.mp4',mimeType:'video/mp4',buffer:Buffer.from('synthetic')});
    await page.locator('#nextStep').click();
    await page.locator('#step2').waitFor({state:'visible'});
}
(async()=>{
    browser = await chromium.launch({headless:true,channel:'chrome'});
    try {
        await check('General default has no required client, solution or technical stage', async()=>{
            await fresh();
            assert.equal(await page.locator('#perfil').inputValue(),'personalizado');
            assert.equal(await page.locator('#cliente').getAttribute('required'),null);
            assert.equal(await page.locator('#solucoes').isVisible(),false);
            assert.equal(await page.locator('#etapaDestino').isVisible(),false);
            await page.locator('#nextStep').click();
            assert.equal(await page.evaluate(()=>document.activeElement.id),'processo');
            assert.match(await page.locator('#processoError').innerText(),/assunto/);
        });
        for (const profile of Object.keys(rules.profiles).filter(key=>key!=='processo')) {
            await check(profile+': context, review, guide and details follow the profile',async()=>{
                await fresh();
                await page.locator('#perfil').selectOption(profile);
                await page.locator('#processo').fill('Comunicação com a equipe');
                await page.locator('input[name=publico][value=equipe]').check();
                await page.locator('#detalhamento').selectOption('detalhado');
                const value = await page.evaluate(()=>window.DiscoveryContextForm.getValue());
                assert.equal(value.perfil,profile);
                assert.ok(value.guia.includes('Perfil: '+rules.profiles[profile].label));
                assert.doesNotMatch(value.guia,/Solução em vista|potencial de automação|quem vai construir o robô/);
                await page.locator('#nextStep').click();
                assert.equal(await page.locator('#step3').isVisible(),true);
                assert.ok((await page.locator('#reviewStructured').innerText()).includes(rules.profiles[profile].label));
                assert.match(await page.locator('#reviewDetail').innerText(),/Detalhado/);
                assert.equal((await page.locator('#cliente').inputValue()),'');
            });
        }
        await check('Switching profiles preserves manual guide and restores selected deliverables',async()=>{
            await fresh();
            await page.locator('#processo').fill('Pesquisa de comunicação');
            await page.locator('input[name=publico][value=equipe]').check();
            await page.locator('input[name=entregaveis][value=decisoes]').uncheck();
            await page.locator('#toggleGuide').click();
            await page.locator('#editGuide').click();
            await page.locator('#context').fill('Manter somente os relatos sobre a campanha. Não atribuir nomes.');
            await page.locator('#perfil').selectOption('pesquisa');
            assert.match(await page.locator('#context').inputValue(),/Não atribuir nomes/);
            assert.equal(await page.locator('#guideEditedNotice').isVisible(),true);
            await page.locator('#perfil').selectOption('personalizado');
            assert.equal(await page.locator('input[name=entregaveis][value=decisoes]').isChecked(),false);
            await page.reload();
            assert.equal((await page.evaluate(async()=>{await window.DiscoveryContextForm.ready;return window.DiscoveryContextForm.getValue();})).perfil,'personalizado');
        });
        await check('AI guide improvement accepts general requests without a client',async()=>{
            await fresh();
            await page.locator('#processo').fill('Treinamento de comunicação');
            await page.locator('#toggleGuide').click();
            let submitted;
            await page.route('**/api/prompt/suggest',async route=>{
                submitted = route.request().postDataJSON();
                await route.fulfill({json:{ok:true,prompt:'Organize os conceitos de comunicação, os exemplos apresentados e as dúvidas da equipe.'}});
            });
            await page.locator('#suggestPrompt').click();
            await page.waitForFunction(()=>window.DiscoveryContextForm.getValue().guiaEditado);
            assert.equal(submitted.contexto.perfil,'personalizado');
            assert.equal(submitted.contexto.cliente,'');
            assert.match(await page.locator('#context').inputValue(),/Organize os conceitos/);
        });
        await check('Legacy structured draft retains process profile and original guide',async()=>{
            await fresh({version:2,contexto:{cliente:'Cliente sintético',processo:'Pedidos',solucoes:['rpa'],etapaDestino:'spec_rpa',publico:['rpa'],entregaveis:['fluxo_atual'],entregaveisTocado:true,guiaEditado:true,guia:'Meu guia antigo intacto.'}});
            assert.equal(await page.locator('#perfil').inputValue(),'processo');
            assert.equal(await page.locator('#solucoes').isVisible(),true);
            assert.equal(await page.locator('#context').inputValue(),'Meu guia antigo intacto.');
        });
        await check('Real synthetic upload persists profile and general context without client',async()=>{
            await fresh();
            await page.locator('#perfil').selectOption('reuniao');
            await page.locator('#processo').fill('[QA sintético] Alinhamento de Marketing');
            await page.locator('input[name=publico][value=equipe]').check();
            await page.locator('#nextStep').click();
            await page.locator('#approved').check();
            const pending = page.waitForResponse(r=>r.url().endsWith('/api/jobs/upload')&&r.request().method()==='POST');
            await page.locator('#submitJob').click();
            const response = await pending, job=await response.json();
            assert.equal(response.status(),201);
            assert.equal(job.contexto.perfil,'reuniao');
            assert.equal(job.contexto.cliente,'');
            assert.ok(job.process_context.includes('Perfil: Reunião'));
        });
        for (const profile of Object.keys(rules.profiles).filter(key=>key!=='processo')) {
            await check(profile+': separate previews play, downloads and HTML match the profile',async()=>{
                await page.goto(base+'/#job=qa-'+profile);
                await page.locator('#previewStack video').first().waitFor();
                assert.equal(await page.locator('#previewStack video').count(),2);
                await page.locator('#previewStack video').first().evaluate(video=>video.play());
                await page.waitForFunction(()=>document.querySelector('#previewStack video')?.currentTime>0.2);
                const media = await page.locator('#previewStack video').first().evaluate(video=>{video.pause();return {time:video.currentTime,error:video.error?.code};});
                assert.ok(media.time>0); assert.equal(media.error,undefined);
                await page.locator('#tabDocuments').click();
                const detail=await (await page.request.get(base+'/api/jobs/qa-'+profile)).json();
                assert.ok(detail.documents.some(d=>d.filename===rules.profiles[profile].filename&&d.available));
                assert.ok(!detail.documents.some(d=>d.filename==='requisitos-rpa.md'));
                for(const document of detail.documents.filter(d=>d.available)) assert.equal((await page.request.get(base+document.url)).status(),200);
                const report=await context.newPage();
                await report.goto(base+'/api/jobs/qa-'+profile+'/report');
                assert.ok((await report.locator('body').innerText()).includes(rules.profiles[profile].document.toUpperCase()));
                assert.equal(await report.locator('a[href*=requisitos-rpa]').count(),0);
                assert.equal(await report.locator('a[href="documentacao.docx"]').count(),1);
                for(const width of [1440,375]){
                    await report.setViewportSize({width,height:1000});
                    assert.ok(await report.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
                    if(profile==='reuniao')await report.screenshot({path:path.join(output,'report-'+width+'.png'),fullPage:true});
                }
                await report.close();
            });
        }
        await check('Desktop/mobile profile form has keyboard access and no overflow',async()=>{
            await fresh();
            await page.locator('#perfil').focus();
            assert.equal(await page.evaluate(()=>document.activeElement.id),'perfil');
            await page.locator('#processo').fill('Alinhamento entre Marketing, Pessoas e Operações');
            await page.locator('input[name=publico][value=equipe]').check();
            for(const width of [1440,375]){
                await page.setViewportSize({width,height:1000});
                assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
                await page.locator('#form').screenshot({path:path.join(output,'context-'+width+'.png')});
            }
        });
        await check('Guardrails: empty history offers creation; filters offer reset; discard is explicit',async()=>{
            await page.route('**/api/jobs',route=>route.fulfill({json:[]}));
            await page.goto(base+'/#history');
            await page.getByRole('link',{name:'Criar primeira análise'}).waitFor();
            await page.locator('#searchJobs').fill('sem-resultados');
            await page.locator('#resetFilters').click();
            assert.equal(await page.locator('#searchJobs').inputValue(),'');
            await page.unroute('**/api/jobs');
            await page.reload();
            await page.locator('#clearQueue:not([disabled])').click();
            await page.locator('#confirmDialog').waitFor({state:'visible'});
            assert.match(await page.locator('#confirmMessage').innerText(),/não pode ser desfeita/);
            assert.equal(await page.locator('#acceptConfirm').innerText(),'Excluir esses trabalhos');
            await page.locator('#rejectConfirm').click();
            assert.deepEqual(errors,[]);
        });
    } finally {
        fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({results,errors},null,2));
        await browser.close();
    }
    console.log(JSON.stringify({passed:results.filter(r=>r.status==='PASS').length,failed:results.filter(r=>r.status==='FAIL').length,output}));
    process.exitCode=results.some(r=>r.status==='FAIL')?1:0;
})().catch(error=>{console.error(error);process.exit(1);});
