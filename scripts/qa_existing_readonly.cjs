/* Read-only acceptance against the existing local history. No POST requests. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const base=process.env.QA_EXISTING_URL||'http://127.0.0.1:8770';
 const output=path.resolve('cache','ui-qa-evidence');fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const page=await context.newPage();page.setDefaultTimeout(12000);
 const mutations=[];page.on('request',r=>{if(r.method()!=='GET')mutations.push(r.method());});
 try{
  const health=await (await context.request.get(base+'/api/health')).json();
  const jobs=await (await context.request.get(base+'/api/jobs')).json();
  assert.ok(Array.isArray(jobs));
  await page.goto(base+'/#new');await page.waitForFunction(()=>document.querySelector('#healthLabel').textContent!=='Conectando…');await page.evaluate(()=>document.fonts.ready);
  await page.screenshot({path:path.join(output,'final-new-desktop.png'),fullPage:true});
  await page.setViewportSize({width:375,height:1000});await page.screenshot({path:path.join(output,'final-new-mobile.png'),fullPage:true});
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(base+'/#history');await page.locator('#historyStats .stat-card').first().waitFor();
  assert.equal(await page.locator('#historyStats .stat-card').nth(2).locator('strong').innerText(),String(jobs.filter(j=>j.status==='COMPLETED'&&!j.delivery_missing).length));
  assert.equal(await page.locator('#historyStats .stat-card').nth(3).locator('strong').innerText(),String(jobs.filter(j=>j.status==='FAILED'||j.delivery_missing).length));
  let missingChecked=0,retryBlocked=0;
  for(const job of jobs){
   if(!job.delivery_missing&&job.can_retry!==false)continue;
   await page.goto(base+'/#job='+encodeURIComponent(job.id));await page.waitForFunction(()=>document.querySelector('#detailTitle').textContent!=='Carregando análise…');
   if(job.delivery_missing){
    assert.match(await page.locator('#previewStack').innerText(),/arquivos desta entrega não estão aqui/);
    assert.equal(await page.locator('#package').isVisible(),false);assert.equal(await page.locator('#rebuildDocs').isVisible(),false);assert.equal(await page.locator('#reuseRequest').isEnabled(),true);missingChecked++;
   }
   if(['FAILED','CANCELLED'].includes(job.status)&&job.can_retry===false){
    assert.equal(await page.locator('#retryJob').isDisabled(),true);assert.equal(await page.locator('#reuseRequest').isEnabled(),true);retryBlocked++;
   }
  }
  assert.deepEqual(mutations,[]);
  const result={mode:'readonly',jobCount:jobs.length,missingDeliveriesChecked:missingChecked,retriesWithoutSourcesBlocked:retryBlocked,health:{worker:health.worker,ffmpeg:health.ffmpeg,ffprobe:health.ffprobe,api_configured:health.api_configured},mutations:mutations.length};
  fs.writeFileSync(path.join(output,'existing-readonly-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
