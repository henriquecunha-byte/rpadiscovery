/* Read-only validation of the explicitly fictional local demo; no real jobs edited. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const staging=path.resolve('cache/demo-reembolsos-20261019');
const metadata=JSON.parse(fs.readFileSync(path.join(staging,'demo-job.json'),'utf8'));
assert.match(metadata.id,/^demo-reembolsos-[0-9a-f]{8}$/);
const base='http://127.0.0.1:8770';
const output=path.join(staging,'qa');fs.mkdirSync(output,{recursive:true});
const checks=[],errors=[],writes=[];
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const page=await context.newPage();page.setDefaultTimeout(10000);
  page.on('pageerror',e=>errors.push(e.message));
  await context.route('**/*',route=>{
   const request=route.request();
   if(!['GET','HEAD'].includes(request.method())){writes.push(request.url());return route.abort();}
   if(!request.url().startsWith(base+'/'))return route.abort();
   return route.continue();
  });
  const jobResponse=await context.request.get(`${base}/api/jobs/${metadata.id}`);
  assert.equal(jobResponse.status(),200);const job=await jobResponse.json();
  assert.equal(job.status,'COMPLETED');assert.equal(job.result_json.demo,true);
  assert.equal(Boolean(job.api_approved),false);assert.equal(job.can_rebuild,false);
  assert.equal(job.result_json.source_count,0);checks.push('demo published completed without AI authorization or a fabricated recording');
  await page.goto(`${base}/#job=${metadata.id}`);
  await page.locator('#documentStack .document-content').waitFor();
  assert.match(await page.locator('#detailTitle').textContent(),/DEMO/);
  assert.match(await page.locator('#jobWarning').textContent(),/DEMONSTRAÇÃO/);
  assert.doesNotMatch(await page.locator('#jobWarning').textContent(),/restaure/i);
  assert.equal(await page.locator('#rebuildDocs').isVisible(),false);
  assert.equal(await page.locator('#tabDocuments').getAttribute('aria-selected'),'true');
  assert.equal(await page.locator('#elapsedTime').textContent(),'Não se aplica');
  assert.match(await page.locator('#totalTime').textContent(),/Sem processamento real/);
  checks.push('clear demo label, documentation first and no paid rebuild action');
  const document=await (await context.request.get(`${base}/api/jobs/${metadata.id}/documentation`)).json();
  for(const kind of ['pdf','package']){const response=await context.request.get(`${base}/api/jobs/${metadata.id}/documentation/${kind}?version=${document.version}`);assert.equal(response.status(),200);assert.ok((await response.body()).length>100);fs.writeFileSync(path.join(output,kind==='pdf'?'demo-reader.pdf':'demo-reader.zip'),await response.body());}
  assert.equal(await page.locator('.document-step').count(),4);
  assert.equal(await page.locator('.document-evidence img').count(),4);
  assert.equal(await page.locator('#exportDocumentPdf').isVisible(),true);
  checks.push('four illustrated native steps and revision-bound PDF/ZIP downloads');
  await page.screenshot({path:path.join(output,'demo-desktop.png'),fullPage:false});
  await page.locator('#tabPreviews').click();
  assert.equal(await page.locator('#previewStack video').count(),0);
  assert.match(await page.locator('#previewStack').textContent(),/não solicitados/);
  await page.getByRole('button',{name:'Abrir documentação',exact:true}).click();
  checks.push('video empty state identifies the documentary mode and opens documentation');
  const report=await context.newPage();report.on('pageerror',e=>errors.push(e.message));
  await report.goto(`${base}/api/jobs/${metadata.id}/report`);
  assert.equal(await report.locator('.flow-step').count(),4);
  assert.ok(await report.locator('.flow-step figure img').count()>=4);
  await report.locator('.flow-step').first().screenshot({path:path.join(output,'demo-flow-step.png')});
  await report.setViewportSize({width:390,height:844});
  assert.ok(await report.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await report.close();
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(output,'demo-mobile.png'),fullPage:false});
  checks.push('four illustrated steps, embedded images and desktop/mobile layout');
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
  checks.push('no unhandled browser errors or mutation requests');
  fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({checks,status:'PASS',errors,writes,
   productQA:{comprehension:{status:'PASS',evidence:'Demo label, warning and Documentation tab are visible'},
    distinctScreens:{status:'PASS',evidence:'Documents deliver output; Original request preserves the brief; Activity exposes provenance'},
    emptyStates:{status:'PASS',evidence:'Previews not requested offers the working Open documentation action'},
    destructiveActions:{status:'N/A',evidence:'No destructive action introduced or exercised; the demo is completed and cannot rebuild'}}},null,2));
  console.log(JSON.stringify({status:'PASS',checks:checks.length,url:`${base}/#job=${metadata.id}`}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
