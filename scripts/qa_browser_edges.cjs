/* Edge-case UI regressions: all Drive/API effects are intercepted locally. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const output=path.resolve('cache','ui-qa-evidence'),base='http://127.0.0.1:8772';
const root=process.argv[2];
if(!root)throw new Error('Pass the synthetic QA_FIXTURES directory.');
const results=[];
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'no-preference'});
 const page=await context.newPage();page.setDefaultTimeout(12000);
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 async function check(name,work){try{await work();results.push({name,status:'PASS'});console.log('PASS '+name);}catch(e){results.push({name,status:'FAIL',error:e.message});console.log('FAIL '+name+': '+e.message);await page.screenshot({path:path.join(output,'edge-failure-'+results.length+'.png'),fullPage:true});}}
 async function confirm(yes=true){await page.locator('#confirmDialog').waitFor({state:'visible'});await page.locator(yes?'#acceptConfirm':'#rejectConfirm').click();await page.locator('#confirmDialog').waitFor({state:'hidden'});}
 try{
 await page.route('**/api/drive/status',r=>r.fulfill({json:{connected:true,configured:true}}));
 await page.route('**/api/drive/files?*',r=>r.fulfill({json:r.request().url().includes('folder_id=folder-1')?[{id:'zip-1',name:'reunioes.zip',size:123456,mimeType:'application/zip'}]:[{id:'folder-1',name:'Reuniões de discovery',mimeType:'application/vnd.google-apps.folder'},{id:'video-1',name:'Trevo.mp4',size:500000,mimeType:'video/mp4'}]}));
 await page.goto(base+'/#new');await page.waitForFunction(()=>document.querySelector('#driveBadge').textContent==='Conectado');
 await check('Folder picker keeps directory structure and deduplicates repeated input',async()=>{
  const folder=path.join(root,'jobs','qa-completed','input');await page.locator('#folderInput').setInputFiles(folder);await page.waitForFunction(()=>document.querySelectorAll('#fileStack .file-row').length===2);
  assert.match(await page.locator('#fileStack').innerText(),/input\/01-reuniao/);
  await page.locator('#folderInput').setInputFiles(folder);assert.equal(await page.locator('#fileStack .file-row').count(),2);
 });
 await check('Directory drop preserves nested paths and reads batches',async()=>{
  await page.evaluate(()=>{
   const fileEntry=name=>({isFile:true,isDirectory:false,name,file:resolve=>resolve(new File(['synthetic'],name,{type:'video/mp4'}))});
   const nested={isFile:false,isDirectory:true,name:'subpasta',createReader(){let read=false;return {readEntries(resolve){resolve(read?[]:[fileEntry('parte-b.mp4')]);read=true;}};}};
   const folder={isFile:false,isDirectory:true,name:'pasta-arrastada',createReader(){let index=0;return {readEntries(resolve){resolve([[fileEntry('parte-a.mp4')],[nested],[]][index++]);}};}};
   const event=new Event('drop',{bubbles:true,cancelable:true});Object.defineProperty(event,'dataTransfer',{value:{items:[{webkitGetAsEntry:()=>folder}],files:[]}});document.querySelector('#dropzone').dispatchEvent(event);
  });
  await page.waitForFunction(()=>document.querySelectorAll('#fileStack .file-row').length===4);
  assert.match(await page.locator('#fileStack').innerText(),/pasta-arrastada\/subpasta\/parte-b.mp4/);
 });
 await check('Very long source names wrap at mobile width',async()=>{
  await page.locator('#videoInput').setInputFiles([{name:'Reuniao-de-discovery-com-nome-longo-'.repeat(5)+'.mp4',mimeType:'video/mp4',buffer:Buffer.from('synthetic')}]);
  await page.setViewportSize({width:375,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(output,'sources-mobile.png'),fullPage:true});await page.setViewportSize({width:1440,height:1000});
 });
 await check('Drive folder navigation and cancelled replacement preserve local sources',async()=>{
  await page.locator('#chooseDrive').click();await page.locator('#driveFiles button').filter({hasText:'Trevo.mp4'}).click();
  await page.locator('#driveFiles button').filter({hasText:'Reuniões de discovery'}).click();await page.locator('#driveFiles button').filter({hasText:'reunioes.zip'}).click();
  assert.match(await page.locator('#driveSelection').innerText(),/2 arquivo/);await page.locator('#confirmDrive').click();await confirm(false);assert.equal(await page.locator('#driveModal').isVisible(),true);
  await page.locator('#closeDrive').click();await page.locator('#driveModal').waitFor({state:'hidden'});assert.match(await page.locator('#fileStack').innerText(),/Arquivo local/);
 });
 await check('Drive selection accepts video plus ZIP with explicit source replacement',async()=>{
  await page.locator('#chooseDrive').click();await page.locator('#driveFiles button').filter({hasText:'Trevo.mp4'}).click();
  await page.locator('#driveFiles button').filter({hasText:'Reuniões de discovery'}).click();await page.locator('#driveFiles button').filter({hasText:'reunioes.zip'}).click();
  await page.locator('#confirmDrive').click();await confirm();await page.locator('#driveModal').waitFor({state:'hidden'});
  assert.equal(await page.locator('#fileStack .file-row').count(),2);assert.match(await page.locator('#fileStack').innerText(),/Google Drive/);
  await page.screenshot({path:path.join(output,'08-drive-selection.png'),fullPage:true});
 });
 await check('Rejected import keeps sources, authorization and editable context',async()=>{
  await page.route('**/api/jobs/drive-import',r=>r.fulfill({status:400,json:{detail:'Teste: arquivo do Drive indisponível.'}}));
  await page.locator('#nextStep').click();await page.locator('#title').fill('QA de importação');await page.locator('#context').fill('Documentar regras e exceções do processo da Trevo.');await page.locator('#nextStep').click();await page.locator('#approved').check();await page.locator('#submitJob').click();
  await page.waitForFunction(()=>document.querySelector('#error').textContent.includes('indisponível'));
  assert.equal(await page.locator('#submitJob').isEnabled(),true);assert.equal(await page.locator('#approved').isChecked(),true);
  await page.locator('#previousStep').click();assert.equal(await page.locator('#context').inputValue(),'Documentar regras e exceções do processo da Trevo.');
 });
 await check('Delayed prompt suggestion cannot overwrite intervening edits without confirmation',async()=>{
  let release;const gate=new Promise(resolve=>release=resolve);
  await page.route('**/api/prompt/suggest',async r=>{await gate;await r.fulfill({json:{prompt:'Sugestão substituta para validar confirmação.',generated:true}});});
  await page.locator('#suggestPrompt').click();await page.locator('#context').fill('Meu guia editado enquanto aguardo a resposta.');release();await confirm(false);
  assert.equal(await page.locator('#context').inputValue(),'Meu guia editado enquanto aguardo a resposta.');
 });
 await check('Context and review are usable at mobile width',async()=>{
  await page.setViewportSize({width:375,height:900});await page.screenshot({path:path.join(output,'context-mobile.png'),fullPage:true});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.locator('#nextStep').click();await page.screenshot({path:path.join(output,'review-mobile.png'),fullPage:true});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 });
 await check('Motion enabled uses branded 320ms entry and closes dialogs safely',async()=>{
  assert.equal(await page.locator('#viewNew').evaluate(e=>getComputedStyle(e).animationDuration),'0.32s');
  await page.locator('#helpButton').click();assert.equal(await page.locator('#helpDialog').evaluate(e=>getComputedStyle(e).animationDuration),'0.32s');
  await page.keyboard.press('Escape');await page.locator('#helpDialog').waitFor({state:'hidden'});assert.equal(await page.evaluate(()=>document.activeElement.id),'helpButton');
 });
 await check('Original-range controls seek into edited preview with readable contrast',async()=>{
  await page.setViewportSize({width:1440,height:1000});await page.goto(base+'/#job=qa-completed');await page.locator('#previewStack summary').first().click();const cut=page.locator('#previewStack button[data-seek]').first();await cut.click();assert.equal(await page.locator('#previewStack video').first().evaluate(v=>v.paused),false);
  const colors=await cut.evaluate(e=>({fg:getComputedStyle(e).color,bg:getComputedStyle(e).backgroundColor}));assert.notEqual(colors.fg,colors.bg);await page.screenshot({path:path.join(output,'09-cut-navigation.png'),fullPage:true});
 });
 await check('404 job shows recovery error and never stale delivery',async()=>{
  await page.goto(base+'/#job=does-not-exist');await page.waitForFunction(()=>document.querySelector('#detailTitle').textContent==='Análise não encontrada');assert.equal(await page.locator('#package').isVisible(),false);assert.equal(await page.locator('#previewStack video').count(),0);
 });
 await check('No uncaught errors in edge scenarios',async()=>assert.deepEqual(errors,[]));
 }finally{await browser.close();fs.writeFileSync(path.join(output,'edge-results.json'),JSON.stringify({results},null,2));console.log(JSON.stringify({passed:results.filter(r=>r.status==='PASS').length,failed:results.filter(r=>r.status==='FAIL').length}));if(results.some(r=>r.status==='FAIL'))process.exitCode=1;}
})().catch(e=>{console.error(e);process.exitCode=1;});
