/* Browser regression suite. Use scripts/qa_server.py (synthetic isolated data).
   NODE_PATH may point to an existing Playwright installation. No app dependency.
   Run: node scripts/qa_browser.cjs --fixtures <QA_FIXTURES> */
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const base = process.env.QA_BASE_URL || 'http://127.0.0.1:8772';
const output = path.resolve('cache', 'ui-qa-evidence');
fs.mkdirSync(output, {recursive:true});
const fixtureIndex = process.argv.indexOf('--fixtures');
const fixtureRoot = fixtureIndex >= 0 ? process.argv[fixtureIndex+1] : null;
const screenshotsOnly = process.argv.includes('--screenshots-only');
const results = [], pageErrors = [];
let browser, context, page;
async function check(name, work) {
 try { await work(); results.push({name,status:'PASS'}); console.log('PASS '+name); }
 catch(error) { results.push({name,status:'FAIL',error:error.message}); console.log('FAIL '+name+': '+error.message); await page.screenshot({path:path.join(output,'failure-'+results.length+'.png'),fullPage:true}).catch(()=>{}); }
}
async function route(hash) { await page.goto(base+'/#'+hash); await page.waitForFunction(()=>document.querySelector('#healthLabel')?.textContent !== 'Conectando…'); }
async function screenshot(name) { await page.screenshot({path:path.join(output,name+'.png'),fullPage:true}); }
async function hasNoOverflow() { const metrics=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));assert.ok(metrics.scroll<=metrics.width+1,JSON.stringify(metrics)); }
async function confirmAction() { await page.locator('#confirmDialog').waitFor({state:'visible'});await page.locator('#acceptConfirm').click();await page.locator('#confirmDialog').waitFor({state:'hidden'}); }
(async()=>{
 browser=await chromium.launch({headless:true,channel:'chrome'});
 context=await browser.newContext({viewport:{width:1440,height:1080},reducedMotion:'reduce'});
 page=await context.newPage();page.setDefaultTimeout(12000);page.on('pageerror',error=>pageErrors.push(error.message));
 await route('new');await page.evaluate(()=>document.fonts.ready);
 await check('Branding fonts and official assets load',async()=>{
  const data=await page.evaluate(()=>({font:getComputedStyle(document.body).fontFamily,weights:[350,500,600].map(w=>document.fonts.check(w+' 16px Branding')),broken:[...document.images].filter(img=>!img.complete||!img.naturalWidth).map(img=>img.src)}));
  assert.match(data.font,/Branding/);assert.deepEqual(data.weights,[true,true,true]);assert.deepEqual(data.broken,[]);
 });
 await screenshot('01-new-desktop');
 for(const width of [375,768,1024,1440]) await check('Responsive new analysis '+width,async()=>{await page.setViewportSize({width,height:1080});await hasNoOverflow();await screenshot('new-'+width);});
 await page.setViewportSize({width:1440,height:1080});
 if(screenshotsOnly){await route('history');await page.locator('#jobs .job').first().waitFor();await screenshot('02-history-desktop');await route('job=qa-completed');await page.locator('#previewStack video').first().waitFor();await screenshot('03-previews-desktop');return;}
 await check('Missing source prevents next step',async()=>{await page.locator('#nextStep').click();assert.equal(await page.locator('#step1').isVisible(),true);assert.ok((await page.locator('#fileNotice').innerText()).length>0);});
 await check('File stack adds incrementally, deduplicates and reports unsupported files',async()=>{
  await page.locator('#videoInput').setInputFiles([{name:'reuniao-a.mp4',mimeType:'video/mp4',buffer:Buffer.from('synthetic-a')},{name:'anotacoes.txt',mimeType:'text/plain',buffer:Buffer.from('note')}]);
  assert.equal(await page.locator('#fileStack .file-stack-item').count(),1);
  await page.locator('#videoInput').setInputFiles([{name:'reuniao-b.mp4',mimeType:'video/mp4',buffer:Buffer.from('synthetic-b')}]);
  assert.equal(await page.locator('#fileStack .file-stack-item').count(),2);
  await page.locator('#fileStack button').first().click();assert.equal(await page.locator('#fileStack .file-stack-item').count(),1);
 });
 await check('Context required; review remains blocked',async()=>{await page.locator('#nextStep').click();await page.locator('#nextStep').click();assert.equal(await page.locator('#step2').isVisible(),true);assert.ok((await page.locator('#titleError').innerText()).length>0);});
 await check('Draft text survives reload but approval and files do not',async()=>{
  await page.locator('#title').fill('QA — Trevo');await page.locator('#context').fill('Manter todas as falas sobre a Trevo, incluindo regras, exceções e decisões.');await page.reload();await page.waitForFunction(()=>document.querySelector('#title').value==='QA — Trevo');assert.equal(await page.locator('#approved').isChecked(),false);assert.equal(await page.locator('#fileStack .file-stack-item').count(),0);
 });
 if(fixtureRoot) await check('Real upload creates one queued job; duplicate click blocked',async()=>{
  await page.locator('#videoInput').setInputFiles(path.join(fixtureRoot,'jobs','qa-completed','input','01-reuniao-sintetica.mp4'));
  await page.locator('#nextStep').click();await page.locator('#nextStep').click();await screenshot('04-review-desktop');
  await page.locator('#submitJob').click();assert.equal(await page.locator('#step3').isVisible(),true);assert.equal(await page.locator('#approved').isChecked(),false);
  await page.locator('#approved').check();let submissions=0;const listener=request=>{if(request.url().endsWith('/api/jobs/upload')&&request.method()==='POST')submissions++;};page.on('request',listener);
  await page.locator('#submitJob').evaluate(button=>{button.click();button.click();});await page.waitForURL(/#job=/);await page.waitForFunction(()=>document.querySelector('#detailBadge')?.textContent.includes('fila'));
  page.off('request',listener);assert.equal(submissions,1);assert.equal(await page.locator('#cancelJob').isVisible(),true);
 });
 await route('history');await page.locator('#jobs .job').first().waitFor();await screenshot('02-history-desktop');
 await check('History searches and filters status',async()=>{await page.locator('#searchJobs').fill('Conciliação');await page.waitForFunction(()=>document.querySelectorAll('#jobs .job').length===1);assert.match(await page.locator('#jobs').innerText(),/Conciliação/);await page.locator('#searchJobs').fill('');await page.locator('#statusFilter').selectOption('COMPLETED');await page.waitForFunction(()=>document.querySelectorAll('#jobs .job').length===1);assert.match(await page.locator('#jobs').innerText(),/Trevo/);await page.locator('#statusFilter').selectOption('all');});
 await route('job=qa-completed');await page.locator('#previewStack video').first().waitFor();await screenshot('03-previews-desktop');
 await check('Separate real previews load and play',async()=>{
  assert.equal(await page.locator('#previewStack video').count(),2);
  for(const video of await page.locator('#previewStack video').all()){
   const result=await video.evaluate(async video=>{if(video.readyState<1)await new Promise((resolve,reject)=>{video.onloadedmetadata=resolve;video.onerror=reject;});video.muted=true;await video.play();return {duration:video.duration,paused:video.paused,width:video.videoWidth};});
   assert.ok(result.duration>0);assert.ok(result.width>0);assert.equal(result.paused,false);
  }
 });
 await check('Polling preserves the active video node and playback',async()=>{
  await page.locator('#previewStack video').first().evaluate(video=>{window.__qaVideo=video;video.currentTime=1;});await page.waitForTimeout(5500);
  const result=await page.evaluate(()=>({same:window.__qaVideo===document.querySelector('#previewStack video'),time:window.__qaVideo.currentTime}));assert.equal(result.same,true);assert.ok(result.time>1);
 });
 await check('Preview HTTP Range supports seeking',async()=>{const src=await page.locator('#previewStack video').first().getAttribute('src');const response=await context.request.get(new URL(src,base).href,{headers:{Range:'bytes=0-127'}});assert.equal(response.status(),206);assert.equal((await response.body()).length,128);});
 await check('Tabs support keyboard and documents download',async()=>{
  await page.locator('#tabPreviews').focus();await page.keyboard.press('ArrowRight');await page.locator('#panelDocuments').waitFor({state:'visible'});assert.equal(await page.locator('#tabDocuments').getAttribute('aria-selected'),'true');
  const links=await page.locator('#documentStack a').evaluateAll(links=>links.map(a=>({url:a.href,label:a.getAttribute('aria-label')})));assert.ok(links.length>=7);
  for(const link of links){const response=await context.request.get(link.url);assert.equal(response.status(),200,link.label);assert.ok((await response.body()).length>0);}
  await screenshot('05-documents-desktop');
 });
 await check('Original context and activity remain readable',async()=>{await page.locator('#tabRequest').click();assert.match(await page.locator('#requestContext').innerText(),/Trevo/);await page.locator('#tabActivity').click();assert.ok(await page.locator('#events li').count()>0);});
 await check('Cleanup dialog is keyboard escapable and restores focus',async()=>{await route('history');await page.locator('#clearQueue').waitFor({state:'visible'});await page.locator('#clearQueue').click();await page.locator('#confirmDialog').waitFor({state:'visible'});await page.keyboard.press('Escape');await page.locator('#confirmDialog').waitFor({state:'hidden'});assert.equal(await page.evaluate(()=>document.activeElement.id),'clearQueue');});
 await check('Cancel queued job and retry using retained inputs',async()=>{await route('job=qa-queued');await page.locator('#cancelJob').waitFor({state:'visible'});await page.locator('#cancelJob').click();await confirmAction();await page.waitForFunction(()=>document.querySelector('#detailBadge')?.textContent==='Cancelado');await page.locator('#retryJob').click();await confirmAction();await page.waitForFunction(()=>document.querySelector('#detailBadge')?.textContent.includes('fila'));});
 await check('Failed job exposes recovery and original error',async()=>{await route('job=qa-failed');await page.locator('#retryJob').waitFor({state:'visible'});assert.match(await page.locator('#detailError').innerText(),/indisponível/);await screenshot('06-failed-desktop');});
 await route('settings');await check('Unconfigured Drive does not offer invalid OAuth action',async()=>{await page.waitForFunction(()=>document.querySelector('#driveBadge')?.textContent==='Configurar');assert.equal(await page.locator('#connectDrive').isVisible(),false);assert.ok((await page.locator('#driveStatus').innerText()).length>0);});await screenshot('07-settings-desktop');
 await check('Reduced motion is honored',async()=>{const result=await page.evaluate(()=>({reduced:matchMedia('(prefers-reduced-motion: reduce)').matches,animation:getComputedStyle(document.querySelector('#viewSettings')).animationName}));assert.equal(result.reduced,true);assert.equal(result.animation,'none');});
 for(const width of [375,768,1024,1440]) for(const target of ['history','job=qa-completed','settings']) await check('Responsive '+target+' '+width,async()=>{await page.setViewportSize({width,height:1000});await route(target);if(target.startsWith('job'))await page.locator('#previewStack video').first().waitFor();await hasNoOverflow();if(width===375)await screenshot(target.replace('=','-')+'-mobile');});
 await check('Dynamic names are text, never executable markup',async()=>{
  await page.route('**/api/jobs',route=>route.fulfill({json:[{id:'xss-check',title:'<img src=x onerror="window.__xss=1">',process_context:'safe',status:'FAILED',stage:'<svg onload="window.__xss=2">',created_at:new Date().toISOString(),progress:0}]}));await route('history');await page.waitForFunction(()=>document.querySelector('#jobs')?.textContent.includes('onerror'));assert.equal(await page.evaluate(()=>window.__xss),undefined);assert.equal(await page.locator('#jobs img,#jobs svg[onload]').count(),0);await page.unroute('**/api/jobs');
 });
 await check('No uncaught JavaScript errors',async()=>assert.deepEqual(pageErrors,[]));
})().catch(error=>{results.push({name:'Suite setup',status:'FAIL',error:error.stack});console.error(error);}).finally(async()=>{
 fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({base,synthetic:true,date:new Date().toISOString(),results,pageErrors},null,2));
 if(browser)await browser.close();const failed=results.filter(r=>r.status==='FAIL').length;console.log(JSON.stringify({passed:results.length-failed,failed,output}));if(failed)process.exitCode=1;
});
