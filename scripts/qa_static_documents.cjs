/* Isolated synthetic server only. No real Google OAuth or upload is performed. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.QA_BASE_URL || 'http://127.0.0.1:8772';
const output = path.resolve('cache/static-document-ui-qa');
fs.mkdirSync(output,{recursive:true});
const results = [], errors = [];
(async()=>{
 const browser = await chromium.launch({headless:true,channel:'chrome'});
 const context = await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const page = await context.newPage();page.setDefaultTimeout(10000);
 page.on('pageerror',error=>errors.push(error.message));
 async function check(name, work){try{await work();results.push({name,status:'PASS'});console.log('PASS '+name);}catch(error){results.push({name,status:'FAIL',error:error.message});console.log('FAIL '+name+': '+error.message);}}
 let archived = false, archiveCalls = 0, restoreCalls = 0;
 await page.route('**/api/drive/status',route=>route.fulfill({json:{connected:true,configured:true,default_folder_id:'synthetic-project'}}));
 await page.route(/\/api\/jobs\/qa-documents$/,async route=>{
   const response=await route.fetch();const job=await response.json();
   if(archived) job.drive_storage={asset_count:3,sources_complete:false,webViewLink:'https://drive.google.com/drive/folders/synthetic'};
   await route.fulfill({json:job});
 });
 await page.route('**/api/jobs/qa-documents/drive',async route=>{
   assert.equal(route.request().postDataJSON().include_assets,true);archiveCalls++;archived=true;
   await route.fulfill({json:{asset_count:3,sources_complete:false,webViewLink:'https://drive.google.com/drive/folders/synthetic'}});
 });
 await page.route('**/api/jobs/qa-documents/drive/restore',async route=>{restoreCalls++;await route.fulfill({json:{restored:0}});});
 await check('new requests default to documentation; mode is configurable',async()=>{
   await page.goto(base+'/#new');await page.waitForFunction(()=>window.DiscoveryContextForm?.getValue().perfil);
   assert.equal(await page.locator('#modoEntrega').inputValue(),'documentacao');
   await page.locator('#videoInput').setInputFiles({name:'synthetic.mp4',mimeType:'video/mp4',buffer:Buffer.from('synthetic-qa')});
   await page.locator('#nextStep').click();
   await page.locator('#modoEntrega').selectOption('documentacao_previews');
   assert.equal(await page.evaluate(()=>DiscoveryContextForm.getValue().modoEntrega),'documentacao_previews');
 });
 await check('static delivery opens Documentation, explains optional previews and can rebuild without raw videos',async()=>{
   await page.goto(base+'/#job=qa-documents');await page.locator('#documentStack .document-content').waitFor();
   assert.equal(await page.locator('[data-tab="Documents"]').getAttribute('aria-selected'),'true');
   assert.match(await page.locator('#rebuildDocs').textContent(),/Revisar documentação/);
   assert.equal(await page.locator('#rebuildDocs').isVisible(),true);
   await page.locator('[data-tab="Previews"]').click();
   assert.match(await page.locator('#previewStack').textContent(),/não solicitados/);
   assert.equal(await page.locator('#previewStack video').count(),0);
   await page.getByRole('button',{name:'Abrir documentação',exact:true}).click();
   await page.screenshot({path:path.join(output,'documents-desktop.png'),fullPage:true});
 });
 await check('report displays embedded images offline, no video dependency or horizontal overflow',async()=>{
   const report=await context.newPage();await report.goto(base+'/api/jobs/qa-documents/report');
   await report.locator('figure img').first().waitFor();
   assert.ok(await report.locator('figure img').count()>=2);
   assert.ok(await report.locator('figure img').first().getAttribute('src').then(src=>src.startsWith('data:image/')));
   assert.equal(await report.locator('video').count(),0);
   assert.ok(await report.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await report.setViewportSize({width:390,height:844});
   assert.ok(await report.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await report.screenshot({path:path.join(output,'report-mobile.png'),fullPage:true});await report.close();
 });
 await check('Drive archive and recovery require explicit, specific confirmation',async()=>{
   await page.locator('#archiveDrive').click();await page.locator('#confirmDialog').waitFor({state:'visible'});
   assert.match(await page.locator('#confirmDialog').textContent(),/gravações disponíveis, prints e documentos/);
   assert.equal(archiveCalls,0);await page.locator('#acceptConfirm').click();
   await page.waitForFunction(()=>document.querySelector('#driveMessage').textContent.includes('fontes originais'));
   await page.locator('#restoreDrive').waitFor({state:'visible'});await page.locator('#restoreDrive').click();
   await page.locator('#confirmDialog').waitFor({state:'visible'});
   assert.match(await page.locator('#confirmDialog').textContent(),/não serão sobrescritos/);
   assert.equal(restoreCalls,0);await page.locator('#acceptConfirm').click();
   await page.waitForFunction(()=>document.querySelector('#driveMessage').textContent.includes('recuperado'));
   assert.equal(archiveCalls,1);assert.equal(restoreCalls,1);
 });
 await check('mobile delivery layout fits the viewport',async()=>{
   await page.setViewportSize({width:390,height:844});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.screenshot({path:path.join(output,'documents-mobile.png'),fullPage:true});
 });
 await check('no unhandled browser errors',async()=>assert.deepEqual(errors,[]));
 fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({results,errors},null,2));
 await browser.close();if(results.some(r=>r.status==='FAIL'))process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
