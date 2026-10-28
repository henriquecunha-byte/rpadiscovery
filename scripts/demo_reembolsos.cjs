/* Four fictional evidence screens. No AI, accounts, uploads or real payments. */
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const output = path.resolve(process.argv[2] || 'cache/demo-reembolsos-20261019');
const assets = path.join(output,'evidence');
fs.mkdirSync(assets,{recursive:true});
const field=(name,value)=>`<div class="field"><label>${name}</label><div>${value}</div></div>`;
const row=(name,value)=>`<div class="row"><span>${name}</span><strong>${value}</strong></div>`;
const screens = [
 {title:'Registrar a despesa',step:'01',status:'Rascunho',body:`<div class="grid">${field('Categoria','Transporte')}${field('Centro de custo','Projeto Aurora')}${field('Valor da despesa','R$ 148,60')}${field('Data da despesa','16/10/2026')}</div><div class="note">Motivo: deslocamento para visita ao projeto.</div>`,action:'Salvar e continuar'},
 {title:'Conferir e enviar',step:'02',status:'Pronto para enviar',body:`<div class="rows">${row('Comprovante','recibo-demo.pdf')}${row('Valor informado','R$ 148,60')}${row('Limite ilustrativo por solicitação','R$ 500,00')}${row('Verificação do comprovante','Anexo presente')}</div><div class="note success">Dados completos para solicitar aprovação.</div>`,action:'Enviar para aprovação'},
 {title:'Aprovar a solicitação',step:'03',status:'Aguardando aprovação',body:`<div class="rows">${row('Solicitação','RB-DEMO-0042')}${row('Responsável pela análise','Gestor do projeto')}${row('Categoria e valor','Transporte · R$ 148,60')}${row('Alocação','Projeto Aurora')}</div><div class="note">O gestor confere a despesa e o comprovante antes de decidir.</div>`,action:'Aprovar solicitação',secondary:'Devolver para ajuste'},
 {title:'Programar o reembolso',step:'04',status:'Agendado',body:`<div class="rows">${row('Valor aprovado','R$ 148,60')}${row('Data programada','21/10/2026')}${row('Responsável','Financeiro')}${row('Situação','Agendamento registrado')}</div><div class="note success">A aprovação permanece vinculada à solicitação.</div>`,action:'Agendamento registrado'},
];
const style=`@font-face{font-family:Branding;src:url('/static/btime/fontes/Branding-Medium.woff');font-weight:400 500}@font-face{font-family:Branding;src:url('/static/btime/fontes/Branding-Semibold.woff');font-weight:600 800}*{box-sizing:border-box}body{margin:0;background:#f7f6fb;color:#100b22;font:20px/1.35 Branding,'Segoe UI',sans-serif}header{height:60px;background:#100b22;color:white;display:flex;align-items:center;justify-content:space-between;padding:0 30px}header strong{font-size:21px}.demo{border:1px solid #c7afff;border-radius:6px;padding:4px 12px;font-size:16px;color:#e8ddff}main{padding:22px 30px}small{font-size:16px;color:#62596f}h1{font-size:31px;line-height:1.15;margin:6px 0 18px;letter-spacing:-.03em}.heading{display:flex;justify-content:space-between;align-items:center}.status{font-size:17px;border-radius:7px;background:#f0eaff;color:#571ee6;padding:8px 12px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px 22px}.field label{display:block;font-size:18px;color:#62596f;margin-bottom:6px}.field div{border:1px solid #c8c1d9;border-radius:8px;padding:11px 14px;background:white;font-size:22px}.rows{background:white;border:1px solid #ddd5eb;border-radius:10px;padding:2px 20px}.row{display:flex;justify-content:space-between;align-items:center;min-height:44px;gap:14px;border-bottom:1px solid #eee8f6}.row:last-child{border-bottom:0}.row strong{font-size:20px}.row span{color:#62596f;font-size:18px}.note{margin-top:15px;padding:10px 14px;background:#f0eaff;border-radius:8px;font-size:18px}.success{color:#145638;background:#eaf7f0}footer{position:absolute;bottom:20px;left:30px;right:30px;display:flex;justify-content:space-between;align-items:center;gap:15px}.disclaimer{font-size:14px;color:#62596f;max-width:360px}.actions{display:flex;gap:12px}.button{font-size:18px;background:#571ee6;color:white;border-radius:8px;padding:12px 16px;white-space:nowrap}.secondary{color:#571ee6;background:white;border:1px solid #c7b1ff}`;
(async()=>{
 const browser = await chromium.launch({headless:true,channel:'chrome'});
 try {
  const context=await browser.newContext({viewport:{width:900,height:540},deviceScaleFactor:2});
  const page=await context.newPage();
  for(let i=0;i<screens.length;i++){
   const screen=screens[i];
   await page.route('**/__fictional_expense_screen__',route=>route.fulfill({contentType:'text/html',body:`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>${style}</style></head><body><header><strong>Portal de despesas fictício</strong><span class="demo">DEMONSTRAÇÃO</span></header><main><div class="heading"><small>ETAPA ${screen.step} · RB-DEMO-0042</small><span class="status">${screen.status}</span></div><h1>${screen.title}</h1>${screen.body}</main><footer><span class="disclaimer">Telas e dados ilustrativos. Nenhuma despesa ou transação real.</span><div class="actions">${screen.secondary?`<span class="button secondary">${screen.secondary}</span>`:''}<span class="button">${screen.action}</span></div></footer></body></html>`}));
   await page.goto('http://127.0.0.1:8770/__fictional_expense_screen__');
   await page.evaluate(()=>document.fonts.ready);
   await page.screenshot({path:path.join(assets,`demo-tela-${i+1}.png`)});
   await page.unroute('**/__fictional_expense_screen__');
  }
  console.log(JSON.stringify({screens:screens.length,directory:assets}));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
