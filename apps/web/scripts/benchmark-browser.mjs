// Run while scripts.benchmark_features is reviewing documents.
// PLAYWRIGHT_MODULE may point to an existing Playwright installation.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
import { writeFile } from 'node:fs/promises';
import { performance } from 'node:perf_hooks';
const browser = await chromium.launch({headless:true});
const base='http://127.0.0.1:5173';
const api='http://127.0.0.1:18000';
const results={transport:'Production build, headless Chromium, desktop 1440x1000, loopback',measurements:[],errors:[]};
const out=new URL('../../../reports/browser-benchmark-2026-09-07.json', import.meta.url);
const save=()=>writeFile(out,JSON.stringify(results,null,2));
async function timed(name,fn){
 const start=performance.now();
 try{await fn();results.measurements.push({feature:name,ms:performance.now()-start,status:'passed'});}
 catch(e){results.measurements.push({feature:name,ms:performance.now()-start,status:'failed',error:e.message.slice(0,300)});}
 console.log(JSON.stringify(results.measurements.at(-1)));await save();
}
let context;
try{
 context=await browser.newContext({viewport:{width:1440,height:1000}});
 const login=await context.request.get(api+'/auth/dev-login?email=benchmark@example.invalid',{maxRedirects:0});
 const token=new URL(login.headers().location).searchParams.get('token');
 await context.close();
 for(const [path,selector,apiPath] of [
 ['/login','text=Sign in to your workspace',null],
 ['/manual','input[type=file]','/contracts'],
 ['/playbook','h1','/playbook'],
 ['/system','h1','/health/db'],
 ['/evaluate','h1',null],
 ]){
  for(let n=1;n<=3;n++){
   context=await browser.newContext({viewport:{width:1440,height:1000}});
   if(path!='/login')await context.addInitScript(t=>localStorage.setItem('access_token',t),token);
   const page=await context.newPage();
   page.on('pageerror',e=>results.errors.push({path,error:e.message}));
   await timed('Cold page '+path+' run '+n,async()=>{
    const response=apiPath?page.waitForResponse(r=>new URL(r.url()).pathname===apiPath&&r.status()===200):Promise.resolve();
    await page.goto(base+path,{waitUntil:'domcontentloaded'});
    await response;
    await page.locator(selector).first().waitFor({state:path==='/manual'?'attached':'visible'});
    await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
   });
   await context.close();
  }
 }
 context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(t=>localStorage.setItem('access_token',t),token);
 const page=await context.newPage();
 page.on('pageerror',e=>results.errors.push({path:'contract',error:e.message}));
 let report;
 for(let n=0;n<120;n++){
  const response=await context.request.get(api+'/contracts',{headers:{Authorization:'Bearer '+token}});
  const reports=await response.json();
  if(reports.length){report=reports[0];break;}
  await new Promise(r=>setTimeout(r,3000));
 }
 if(report){
  await timed('Open real AI report workspace',async()=>{
   const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/contracts/'+report.report_id&&r.status()===200);
   await page.goto(base+'/contract?report='+report.report_id,{waitUntil:'domcontentloaded'});
   await response;
   await page.getByText('Original Contract',{exact:true}).waitFor();
   await page.locator('main button').first().waitFor();
  });
  await timed('Open clause analysis panel',async()=>{
   await page.locator('main button').first().click();
   await page.getByRole('button',{name:'Accept Risk',exact:true}).waitFor();
  });
  await timed('Accept clause in browser',async()=>{
   const response=page.waitForResponse(r=>r.url().endsWith('/accept')&&r.request().method()==='POST');
   await page.getByRole('button',{name:'Accept Risk',exact:true}).click();
   const r=await response;if(r.status()!==200)throw Error('accept '+r.status());
   await page.getByRole('button',{name:'✓ Accepted — Undo',exact:true}).waitFor();
  });
  await timed('Withdraw acceptance in browser',async()=>{
   await page.getByRole('button',{name:'✓ Accepted — Undo',exact:true}).click();
   await page.getByRole('button',{name:'Accept Risk',exact:true}).waitFor();
  });
  await page.screenshot({path:new URL('../../../reports/benchmark-contract-desktop.png', import.meta.url).pathname,fullPage:true});
 }else results.errors.push({error:'No report available within six minutes'});
 await context.close();
}finally{await browser.close();await save();}
