/* No real accounts or cloud requests. Future-provider scenarios are explicit browser mocks. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path');
const base=process.env.QA_BASE_URL||'http://127.0.0.1:8772';
const output=path.resolve('cache/auth-qa-evidence');
fs.mkdirSync(output,{recursive:true});
const results=[];
const future={mode:'required',provider:'supabase',status:'ready',enabled:true,can_continue_local:false};
const anonymous={authenticated:false,user:null};
const user={id:'synthetic-user',email:'qa@example.test'};
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 async function scenario(name,work){
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const page=await context.newPage();page.setDefaultTimeout(8000);
  const errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push({url:r.url(),method:r.method()}));
  try{await work(page,context,requests);assert.deepEqual(errors,[]);results.push({name,status:'PASS'});console.log('PASS '+name);}
  catch(e){results.push({name,status:'FAIL',error:e.message,pageErrors:errors});console.log('FAIL '+name+': '+e.message);await page.screenshot({path:path.join(output,'failure-'+results.length+'.png'),fullPage:true}).catch(()=>{});}
  finally{await context.close();}
 }
 async function load(page,hash=''){await page.goto(base+'/'+hash);await page.waitForFunction(()=>window.DiscoveryAuth);await page.evaluate(()=>window.DiscoveryAuth.ready);await page.evaluate(()=>window.DiscoveryContextForm.ready);}
 async function mockProvider(page,{config=future,session=anonymous}={}){
  await page.route('**/api/auth/config',r=>r.fulfill({json:config}));
  await page.route('**/api/auth/session',r=>r.fulfill({json:typeof session==='function'?session():session}));
 }
 const business=requests=>requests.filter(r=>new URL(r.url).pathname.startsWith('/api/')&&!new URL(r.url).pathname.startsWith('/api/auth/'));
 try{
  await scenario('Local: root opens honest inactive login, without workspace requests or polling',async(page,context,requests)=>{
   await load(page);assert.match(page.url(),/#login$/);assert.equal(await page.locator('#loginEmail').isDisabled(),true);
   assert.equal(await page.locator('#loginSubmit').isDisabled(),true);assert.equal(await page.locator('#continueLocal').isVisible(),true);
   assert.equal(await page.locator('.app-shell').isVisible(),false);assert.match(await page.locator('#authAvailabilityText').innerText(),/Supabase/);
   await page.waitForTimeout(5500);assert.equal(business(requests).length,0);
   await page.screenshot({path:path.join(output,'login-desktop.png'),fullPage:true});
  });
  await scenario('Recovery: unavailable state never claims email was sent',async page=>{
   await load(page,'#forgot-password');assert.match(await page.locator('#authTitle').innerText(),/Recuperar/);
   assert.equal(await page.locator('#recoverSubmit').isDisabled(),true);assert.equal(await page.locator('#authMessage').isVisible(),false);
   await page.locator('#recoverForm a').click();await page.locator('#loginForm').waitFor({state:'visible'});
  });
  await scenario('Skip link focuses auth content without changing route or granting access',async(page,context,requests)=>{
   await load(page,'#login');await page.locator('.skip-link').focus();await page.keyboard.press('Enter');
   assert.match(page.url(),/#login$/);assert.equal(await page.evaluate(()=>document.activeElement.id),'authMain');
   assert.equal(await page.evaluate(()=>window.DiscoveryAuth.canAccess()),false);assert.equal(business(requests).length,0);
  });
  await scenario('Responsive login: 320, 375, 768 and 1440 px; keyboard access',async page=>{
   await load(page);
   for(const width of [320,375,768,1440]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
   await page.setViewportSize({width:375,height:900});await page.screenshot({path:path.join(output,'login-mobile.png'),fullPage:true});
   await page.locator('#continueLocal').focus();assert.equal(await page.locator('#continueLocal').evaluate(e=>e===document.activeElement),true);
   await page.keyboard.press('Enter');await page.locator('#viewNew').waitFor({state:'visible'});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  });
  await scenario('Local exit clears only app-owned drafts, stops polling and leaves server jobs untouched',async(page,context,requests)=>{
   await load(page,'#new');await page.locator('#healthLabel').filter({hasText:'Ambiente pronto'}).waitFor().catch(()=>{});
   await page.evaluate(()=>{localStorage.setItem('unrelated-test','keep');localStorage.setItem('btime.discovery.draft.v1','{}');localStorage.setItem('btime.discovery.drive-folder','test-folder');document.querySelector('#processo').value='Private process';document.querySelector('#processo').dispatchEvent(new Event('input',{bubbles:true}));});
   const count=await page.request.get(base+'/api/jobs').then(r=>r.json()).then(j=>j.length);
   await page.locator('#logoutButton').click();await page.locator('#authView').waitFor({state:'visible'});
   await page.waitForFunction(()=>!document.querySelector('#continueLocal').disabled);
   assert.equal(await page.locator('#processo').inputValue(),'');
   assert.equal(await page.evaluate(()=>window.DiscoveryContextForm.getValue().processo),'');
   assert.deepEqual(await page.evaluate(()=>({draft:localStorage.getItem('btime.discovery.draft.v1'),folder:localStorage.getItem('btime.discovery.drive-folder'),other:localStorage.getItem('unrelated-test')})),{draft:null,folder:null,other:'keep'});
   const n=business(requests).length;await page.waitForTimeout(5500);assert.equal(business(requests).length,n);
   assert.equal(await page.request.get(base+'/api/jobs').then(r=>r.json()).then(j=>j.length),count);
   assert.equal(requests.some(r=>/\/cancel|\/clear/.test(r.url)),false);
  });
  await scenario('Navigating to login stops/removes playing previews',async page=>{
   await load(page,'#job=qa-completed');await page.locator('#previewStack video').first().waitFor();
   await page.locator('#previewStack video').first().evaluate(v=>v.play());
   await page.evaluate(()=>{location.hash='login';});await page.locator('#authView').waitFor({state:'visible'});
   assert.equal(await page.locator('#previewStack video').evaluateAll(videos=>videos.some(v=>!v.paused)),false);
   await page.locator('#continueLocal').click();await page.locator('#previewStack video').first().waitFor();
  });
  await scenario('Required pending config blocks deep links and ignores forged client storage',async(page,context,requests)=>{
   await mockProvider(page,{config:{...future,status:'not_configured',enabled:false}});
   await context.addInitScript(()=>localStorage.setItem('supabase.auth.token','forged'));
   await load(page,'#job=qa-completed');assert.match(page.url(),/#login$/);
   assert.equal(await page.locator('#continueLocal').isVisible(),false);assert.equal(await page.locator('#loginSubmit').isDisabled(),true);
   assert.equal(business(requests).length,0);
   await page.screenshot({path:path.join(output,'login-required.png'),fullPage:true});
  });
  await scenario('Configuration outage fails closed and can be retried',async page=>{
   await page.route('**/api/auth/config',r=>r.fulfill({status:503,json:{detail:'offline'}}));
   await load(page,'#new');assert.equal(await page.locator('#retryAuth').isVisible(),true);assert.equal(await page.locator('#continueLocal').isVisible(),false);
   await page.unroute('**/api/auth/config');await page.locator('#retryAuth').click();await page.locator('#continueLocal').waitFor({state:'visible'});
  });
  await scenario('Future mock: invalid credentials use safe error and never store password',async page=>{
   await mockProvider(page);await page.route('**/api/auth/login',r=>r.fulfill({status:401,json:{detail:'sensitive-password-must-not-be-rendered'}}));
   await load(page,'#login');await page.locator('#loginEmail').fill('qa@example.test');await page.locator('#loginPassword').fill('synthetic-password');
   await page.locator('#togglePassword').click();assert.equal(await page.locator('#loginPassword').getAttribute('type'),'text');
   await page.locator('#loginSubmit').click();await page.locator('#authMessage').filter({hasText:'E-mail ou senha inválidos'}).waitFor();
   assert.equal(await page.locator('#loginPassword').inputValue(),'');assert.equal(await page.locator('body').innerText().then(s=>s.includes('sensitive-password')),false);
   assert.equal(await page.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage}).includes('synthetic-password')),false);
  });
  await scenario('Future mock: confirmed server session returns to requested history and signs out',async page=>{
   let signed=false;await mockProvider(page,{session:()=>signed?{authenticated:true,user}:anonymous});
   await page.route('**/api/auth/login',r=>{signed=true;return r.fulfill({json:{ok:true}});});
   await load(page,'#history');await page.locator('#loginEmail').fill('qa@example.test');await page.locator('#loginPassword').fill('synthetic-password');await page.locator('#loginSubmit').click();
   await page.locator('#viewHistory').waitFor({state:'visible'});assert.match(page.url(),/#history$/);assert.equal(await page.locator('#sessionLabel').innerText(),user.email);
   await page.locator('#logoutButton').click();await page.locator('#authView').waitFor({state:'visible'});assert.equal(await page.locator('#continueLocal').isVisible(),false);
  });
  await scenario('Future mock: recovery shows generic account-neutral result',async page=>{
   await mockProvider(page);await page.route('**/api/auth/recover',r=>r.fulfill({json:{ok:true}}));
   await load(page,'#forgot-password');await page.locator('#recoverEmail').fill('qa@example.test');await page.locator('#recoverSubmit').click();
   await page.locator('#authMessage').filter({hasText:'Se houver uma conta'}).waitFor();
   await page.screenshot({path:path.join(output,'recovery-mock.png'),fullPage:true});
  });
  await scenario('Future mock: stale login response cannot leave recovery route',async page=>{
   await mockProvider(page);let release;const gate=new Promise(resolve=>release=resolve);
   await page.route('**/api/auth/login',async r=>{await gate;await r.fulfill({json:{ok:true}}).catch(()=>{});});
   await load(page,'#login');await page.locator('#loginEmail').fill('qa@example.test');await page.locator('#loginPassword').fill('synthetic-password');
   const sent=page.waitForRequest('**/api/auth/login');await page.locator('#loginSubmit').click();await sent;
   await page.evaluate(()=>{location.hash='forgot-password';});await page.locator('#recoverForm').waitFor({state:'visible'});release();
   await page.waitForTimeout(150);assert.match(page.url(),/#forgot-password$/);assert.equal(await page.locator('#loginPassword').inputValue(),'');
  });
  await scenario('Auth rejection clears workspace and cannot fall back to local mode',async page=>{
   await load(page,'#history');await page.locator('#jobs .job-card').first().waitFor().catch(()=>{});
   await page.route('**/api/jobs',r=>r.fulfill({status:503,json:{code:'auth_not_configured',detail:'pending'}}));
   await page.locator('#refresh').click();await page.locator('#authView').waitFor({state:'visible'});
   assert.equal(await page.locator('#continueLocal').isVisible(),false);assert.equal(await page.locator('#jobs').innerText().then(s=>s.includes('Trevo')),false);
  });
  await scenario('Ordinary 503 is not misclassified as logout',async page=>{
   await page.route('**/api/jobs',r=>r.fulfill({status:503,json:{detail:'Serviço temporariamente indisponível'}}));
   await load(page,'#history');await page.locator('#viewHistory').waitFor({state:'visible'});assert.equal(await page.locator('#authView').isVisible(),false);
  });
  await scenario('Slow jobs response cannot repopulate workspace after exit',async page=>{
   let release;const gate=new Promise(resolve=>release=resolve);
   await page.route('**/api/jobs',async r=>{await gate;await r.fulfill({json:[{id:'late-private',title:'Late private job',status:'COMPLETED'}]}).catch(()=>{});});
   await load(page,'#history');await page.locator('#logoutButton').click();await page.locator('#authView').waitFor({state:'visible'});release();
   await page.waitForTimeout(200);assert.equal(await page.locator('#jobs').innerText().then(s=>s.includes('Late private')),false);assert.match(page.url(),/#login$/);
  });
  await scenario('Actual unavailable API rejects credentials without echoing or minting session',async page=>{
   const response=await page.request.post(base+'/api/auth/login',{data:{email:'qa@example.test',password:'synthetic-password'}});
   assert.equal(response.status(),503);assert.equal((await response.text()).includes('synthetic-password'),false);
   assert.equal(response.headers()['set-cookie'],undefined);assert.equal((await page.request.get(base+'/api/auth/session').then(r=>r.json())).authenticated,false);
  });
 }finally{await browser.close();fs.writeFileSync(path.join(output,'report.json'),JSON.stringify({results},null,2));}
 console.log(results.filter(r=>r.status==='PASS').length+'/'+results.length+' passed');
 if(results.some(r=>r.status==='FAIL'))process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});
