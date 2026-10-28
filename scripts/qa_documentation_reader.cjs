/* Disposable fixtures on QA_BASE_URL; no provider, account, or real job mutation. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const base=process.env.QA_BASE_URL||'http://127.0.0.1:8773';
const output=path.resolve('cache/inline-reader-qa');fs.mkdirSync(output,{recursive:true});
const results=[],errors=[];
let browser,context,page;
async function navigate(id){const url=base+'/#job='+id;if(page.url()===url)await page.reload();else await page.goto(url);}
async function check(name,work){try{await work();results.push({name,status:'PASS'});console.log('PASS '+name);}catch(error){results.push({name,status:'FAIL',error:error.message});console.log('FAIL '+name+': '+error.message);await page?.screenshot({path:path.join(output,'failure-'+results.length+'.png'),fullPage:true}).catch(()=>{});}}
async function open(id='qa-documents'){
 await navigate(id);
 await page.locator('#detailTitle').filter({hasText:/./}).waitFor();
 if(!(await page.locator('#panelDocuments').isVisible()))await page.locator('#tabDocuments').click();
 await page.locator('.document-content').waitFor();
}
async function fits(){assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
(async()=>{
 browser=await chromium.launch({headless:true,channel:'chrome'});
 context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',acceptDownloads:true});
 page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));
 await check('complete document is native and visible without downloading or opening another page',async()=>{
  const downloads=[];page.on('download',d=>downloads.push(d));await open();
  assert.equal(await page.locator('#documentStack iframe').count(),0);
  assert.match(await page.locator('.document-content').textContent(),/Conteúdo sintético relacionado às duas telas/);
  assert.ok(await page.locator('.document-evidence img').count()>=2);
  assert.equal(downloads.length,0);assert.equal(context.pages().length,1);
  assert.equal(await page.locator('#exportDocumentPdf').textContent(),'Exportar PDF');
  assert.equal(await page.locator('#downloadDocumentZip').textContent(),'Baixar ZIP');
  assert.equal(await page.locator('#documentStack .document-card').count(),0);
 });
 await check('section navigation and evidence references keep the analysis route',async()=>{
  const hash=await page.evaluate(()=>location.hash);
  await page.locator('.document-outline a').filter({hasText:'Limitações da análise'}).click();
  assert.equal(await page.evaluate(()=>location.hash),hash);
  assert.equal(await page.evaluate(()=>document.activeElement.textContent),'Limitações da análise');
  const references=page.locator('.document-evidence-link');
  if(await references.count()){await references.first().click();assert.equal(await page.evaluate(()=>location.hash),hash);}
 });
 await check('polling preserves the reader node and scroll position',async()=>{
  await page.evaluate(()=>{window.__readerNode=document.querySelector('.document-content');document.querySelector('.document-content').scrollIntoView();window.__readerScroll=scrollY;});
  await page.waitForResponse(response=>response.url().endsWith('/api/jobs/qa-documents')&&response.request().method()==='GET',{timeout:10000});
  assert.equal(await page.evaluate(()=>window.__readerNode===document.querySelector('.document-content')),true);
  assert.ok(await page.evaluate(()=>Math.abs(window.__readerScroll-scrollY)<5));
 });
 await check('PDF exports the open revision and leaves reading in place',async()=>{
  const version=await page.locator('#documentStack').getAttribute('data-version');
  const event=page.waitForEvent('download');await page.locator('#exportDocumentPdf').click();const download=await event;
  const target=path.join(output,'documentacao-exportada.pdf');await download.saveAs(target);
  assert.equal(fs.readFileSync(target).subarray(0,4).toString(),'%PDF');
  assert.equal(await page.locator('#documentStack').getAttribute('data-version'),version);
  assert.match(await page.locator('.document-export-status').textContent(),/PDF exportado/);
  assert.equal(await page.locator('#exportDocumentPdf').isEnabled(),true);
 });
 await check('ZIP is a separate explicit download and formats are disclosed',async()=>{
  const event=page.waitForEvent('download');await page.locator('#downloadDocumentZip').click();const download=await event;
  const target=path.join(output,'documentacao-completa.zip');await download.saveAs(target);
  assert.equal(fs.readFileSync(target).subarray(0,2).toString(),'PK');
  await page.locator('.document-formats summary').click();assert.match(await page.locator('.document-formats').textContent(),/Word.*PDF|PDF.*Word/);
 });
 await check('revision conflict is actionable without silently downloading another document',async()=>{
  await page.route('**/documentation/pdf?*',route=>route.fulfill({status:409,json:{detail:'O documento foi atualizado. Atualize a leitura antes de exportar esta versão.'}}));
  await page.locator('#exportDocumentPdf').click();
  await page.waitForFunction(()=>document.querySelector('.document-export-status')?.textContent.includes('Atualizar documento'));
  assert.equal(await page.locator('#exportDocumentPdf').isEnabled(),true);
  await page.unroute('**/documentation/pdf?*');await page.locator('.document-refresh').click();await page.locator('.document-content').waitFor();
 });
 for(const profile of ['processo','personalizado','reuniao','treinamento','entrevista','pesquisa'])await check(profile+': complete saved profile, no forced RPA sections in general documents',async()=>{
  await open(profile==='processo'?'qa-completed':'qa-'+profile);
  const headings=await page.locator('.document-section h3').allTextContents();
  assert.ok(headings.includes('Resumo executivo'));assert.ok(headings.includes('Limitações da análise'));
  assert.equal(headings.includes('Fluxo operacional'),profile==='processo');
  if(profile!=='processo')assert.ok(await page.locator('.document-item').count()>0);
 });
 await check('saved text, titles and evidence are not interpreted as executable markup',async()=>{
  await page.route('**/api/jobs/qa-documents/documentation',async route=>{const response=await route.fetch();const data=await response.json();data.title='<img src=x onerror="window.__readerXSS=1">';data.documentation.executive_summary='<svg onload="window.__readerXSS=2">';data.evidence[0].url='javascript:window.__readerXSS=3';await route.fulfill({json:data});});
  await open();assert.match(await page.locator('.document-identity h2').textContent(),/onerror/);
  assert.equal(await page.locator('#documentStack img[onerror],#documentStack svg[onload]').count(),0);
  assert.equal(await page.evaluate(()=>window.__readerXSS),undefined);
  assert.equal(await page.locator('img[src^="javascript:"]').count(),0);await page.unroute('**/api/jobs/qa-documents/documentation');
 });
 await check('loading failure offers retry and does not keep refetching at every poll',async()=>{
  let calls=0;await page.route('**/api/jobs/qa-documents/documentation',route=>{calls++;return route.fulfill({status:503,json:{detail:'Documento temporariamente indisponível.'}});});
  await navigate('qa-documents');await page.locator('.document-state h3').filter({hasText:'Não foi possível abrir'}).waitFor();
  await page.waitForResponse(response=>response.url().endsWith('/api/jobs/qa-documents')&&response.request().method()==='GET');
  assert.equal(calls,1);await page.unroute('**/api/jobs/qa-documents/documentation');await page.getByRole('button',{name:'Tentar novamente',exact:true}).click();await page.locator('.document-content').waitFor();
 });
 await check('a delayed document cannot overwrite another analysis',async()=>{
  let release;const gate=new Promise(resolve=>release=resolve);
  await page.route('**/api/jobs/qa-documents/documentation',async route=>{const response=await route.fetch();const data=await response.json();data.documentation.executive_summary='STALE_DOCUMENT_SENTINEL';await gate;await route.fulfill({json:data}).catch(()=>{});});
  const started=page.waitForRequest(request=>request.url().endsWith('/api/jobs/qa-documents/documentation'));
  await navigate('qa-documents');await started;
  await page.goto(base+'/#job=qa-reuniao');await page.locator('#tabDocuments').click();await page.locator('.document-content').waitFor();
  release();await page.unroute('**/api/jobs/qa-documents/documentation');
  assert.doesNotMatch(await page.locator('.document-content').textContent(),/STALE_DOCUMENT_SENTINEL/);
 });
 await check('document supports keyboard navigation and images have meaningful alternatives',async()=>{
  await open();await page.locator('.document-outline summary').focus();await page.keyboard.press('Enter');await page.keyboard.press('Enter');
  await page.locator('.document-outline a').first().focus();await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(()=>document.activeElement.textContent),'Resumo executivo');
  for(const alt of await page.locator('.document-evidence img').evaluateAll(nodes=>nodes.map(n=>n.alt)))assert.ok(alt.length>5);
 });
 for(const width of [320,390,720,1024,1440])await check('reader and controls fit '+width+' px',async()=>{
  await page.setViewportSize({width,height:1000});await fits();
  if(width===390||width===1440){await page.locator('#panelDocuments').screenshot({path:path.join(output,'reader-'+width+'.png')});}
 });
 await check('expanded labels and RTL mirror do not clip controls',async()=>{
  await page.locator('#exportDocumentPdf').evaluate(n=>n.textContent='Exportar uma cópia deste documento como PDF');
  await page.locator('#downloadDocumentZip').evaluate(n=>n.textContent='Baixar o pacote completo de arquivos ZIP');
  await page.setViewportSize({width:390,height:1000});await fits();
  await page.evaluate(()=>document.documentElement.dir='rtl');await fits();await page.evaluate(()=>document.documentElement.dir='ltr');
 });
 await check('PDF failure remains recoverable and never reports a successful export',async()=>{
  await open();await page.route('**/documentation/pdf?*',route=>route.fulfill({status:503,json:{detail:'Não foi possível exportar este documento em PDF. Tente novamente ou baixe o ZIP.'}}));
  await page.locator('#exportDocumentPdf').click();await page.waitForFunction(()=>document.querySelector('.document-export-status')?.textContent.includes('Não foi possível exportar'));
  assert.equal(await page.locator('#exportDocumentPdf').isEnabled(),true);assert.equal(await page.locator('#downloadDocumentZip').isEnabled(),true);await page.unroute('**/documentation/pdf?*');
 });
 await check('no unhandled browser errors',async()=>assert.deepEqual(errors,[]));
 fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({results,errors,synthetic:true},null,2));
})().catch(error=>{results.push({name:'setup',status:'FAIL',error:error.stack});console.error(error);}).finally(async()=>{await browser?.close();const failed=results.filter(r=>r.status==='FAIL').length;console.log(JSON.stringify({passed:results.length-failed,failed}));if(failed)process.exitCode=1;});
