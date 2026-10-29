/* Test the exported context UI, never the production API or database. */
'use strict';
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = 'http://127.0.0.1:8773';
const output = path.resolve('cache','meeting-reconstruction-20261029','ui-qa');
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const page=await context.newPage();
 page.setDefaultTimeout(5000);
 const results=[],errors=[],unexpected=[];
 page.on('pageerror',error=>errors.push(error.message));
 await context.route('**/*',async route=>{
   const request=route.request(),url=new URL(request.url());
   if(url.origin!==base || url.pathname.startsWith('/api/') || request.method()!=='GET'){
     unexpected.push(request.method()+' '+request.url());return route.abort();
   }
   return route.continue();
 });
 async function check(name,fn){
   try{await fn();results.push({name,status:'PASS'});console.log('PASS '+name);}
   catch(error){results.push({name,status:'FAIL',error:error.message});console.log('FAIL '+name+': '+error.message);}
 }
 try{
  await check('All six profiles are available without a service connection',async()=>{
   await page.goto(base+'/?perfil=processo');
   await page.locator('#contextExportForm').waitFor({state:'visible'});
   assert.equal(await page.locator('#perfil option').count(),6);
   assert.equal(await page.locator('#perfil').inputValue(),'processo');
   assert.equal(await page.locator('#budget').count(),0);
   assert.equal(await page.locator('#suggestPrompt').isVisible(),false);
  });
  await check('Initial empty request points to the required client field',async()=>{
   await page.locator('#contextReview').click();
   assert.equal(await page.evaluate(()=>document.activeElement.id),'cliente');
   assert.equal(await page.locator('#contextExportReview').isVisible(),false);
  });
  await check('The demonstrated RPA + integration checklist and systems can be recreated',async()=>{
   await page.locator('#cliente').fill('Cliente de demonstração');
   await page.locator('#processo').fill('Mapeamento do atendimento');
   await page.locator('#objetivo').fill('Documentar o passo a passo e as telas apresentadas.');
   await page.locator('input[name=solucoes][value=rpa]').check();
   await page.locator('input[name=solucoes][value=integracao]').check();
   assert.equal(await page.locator('input[name=etapaDestino][value=spec_rpa]').isChecked(),true);
   await page.locator('input[name=publico][value=rpa]').check();
   for(const system of ['Excel','Google Sheets','WhatsApp']){
    await page.locator('#sistemas').fill(system);await page.locator('#sistemas').press('Enter');
   }
   await page.locator('#dadosSensiveis').check();
   const value=await page.evaluate(()=>window.DiscoveryContextForm.getValue());
   assert.deepEqual(value.solucoes,['rpa','integracao']);
   assert.ok(value.entregaveis.includes('prints_por_tela'));
   assert.deepEqual(value.sistemas,['Excel','Google Sheets','WhatsApp']);
   assert.equal(await page.locator('#etapaDestinoError').innerText(),'');
   assert.equal(await page.locator('#entregaveisError').innerText(),'');
   assert.equal(await page.locator('#etapaDestino [aria-invalid=true]').count(),0);
   assert.equal(await page.locator('#entregaveis [aria-invalid=true]').count(),0);
   assert.match(value.guia,/Mapeamento do atendimento/);
   assert.match(value.guia,/tela a tela|cada passo/i);
   await page.screenshot({path:path.join(output,'context-desktop.png'),fullPage:true});
  });
  await check('Manual checklist is preserved when the objective changes',async()=>{
   await page.locator('input[name=entregaveis][value=campos_io]').uncheck();
   await page.locator('#objetivo').fill('Documentar com foco nas telas e nas exceções.');
   assert.equal(await page.locator('input[name=entregaveis][value=campos_io]').isChecked(),false);
   await page.locator('#resetDeliverables').click();
   assert.equal(await page.locator('input[name=entregaveis][value=campos_io]').isChecked(),true);
  });
  await check('Manual guide requires a specific confirmation before replacement',async()=>{
   await page.locator('#toggleGuide').click();await page.locator('#editGuide').click();
   await page.locator('#context').fill('Preservar somente o atendimento. Não incluir faturamento.');
   await page.locator('#restoreGeneratedGuide').click();
   assert.equal(await page.locator('#guideResetConfirmation').isVisible(),true);
   await page.locator('#cancelGuideReset').click();
   assert.match(await page.locator('#context').inputValue(),/Não incluir faturamento/);
   await page.locator('#restoreGeneratedGuide').click();await page.locator('#confirmGuideReset').click();
   assert.match(await page.locator('#context').inputValue(),/Mapeamento do atendimento/);
  });
  await check('Review contains the category, selected checklist, systems and guide',async()=>{
   await page.locator('#contextReview').click();
   const summary=await page.locator('#contextSummary').innerText();
   for(const text of ['Processo / RPA','Integração entre sistemas','Especificação de RPA','Print de cada tela','Google Sheets'])assert.ok(summary.includes(text),text);
   assert.equal(await page.locator('#contextSensitiveNotice').isVisible(),true);
   assert.equal(await page.evaluate(()=>document.activeElement.id),'contextReviewTitle');
   await page.screenshot({path:path.join(output,'review-desktop.png'),fullPage:true});
  });
  await check('Confirm exports a complete request without an API call or duplicate event',async()=>{
   await page.evaluate(()=>{window.exportedRequests=[];document.addEventListener('discovery:requestready',event=>window.exportedRequests.push(event.detail));});
   await page.locator('#contextConfirm').click();await page.locator('#contextConfirm').click();
   const requests=await page.evaluate(()=>window.exportedRequests);
   assert.equal(requests.length,1);assert.equal(requests[0].contexto.perfil,'processo');
   assert.equal(requests[0].process_context,requests[0].contexto.guia);
   assert.equal(requests[0].title,'Mapeamento do atendimento');
   assert.ok(requests[0].contexto.entregaveis.includes('prints_por_tela'));
  });
  await check('General profiles retain their own categories instead of RPA requirements',async()=>{
   await page.locator('#contextBack').click();
   for(const profile of ['personalizado','reuniao','treinamento','entrevista','pesquisa']){
    await page.locator('#perfil').selectOption(profile);
    assert.equal(await page.locator('#solucoes').isVisible(),false);
    const value=await page.evaluate(()=>window.DiscoveryContextForm.getValue());
    assert.ok(value.entregaveis.length);assert.equal(value.entregaveis.includes('prints_por_tela'),false);
   }
  });
  await check('Mobile layout and keyboard access preserve the demonstrated controls',async()=>{
   await page.locator('#perfil').selectOption('processo');
   await page.setViewportSize({width:375,height:950});
   await page.locator('#perfil').focus();
   assert.equal(await page.evaluate(()=>document.activeElement.id),'perfil');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.screenshot({path:path.join(output,'context-mobile.png'),fullPage:true});
  });
  await check('No console errors, service calls or external assets',async()=>{
   assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
   assert.deepEqual(await page.evaluate(()=>({local:localStorage.length,session:sessionStorage.length})),{local:0,session:0});
  });
 }finally{
  fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({results,errors,unexpected},null,2));
  await browser.close();
 }
 console.log(JSON.stringify({passed:results.filter(r=>r.status==='PASS').length,failed:results.filter(r=>r.status==='FAIL').length,output}));
 process.exitCode=results.some(r=>r.status==='FAIL')?1:0;
})().catch(error=>{console.error(error);process.exit(1)});
