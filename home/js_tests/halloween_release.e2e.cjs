/* Real package validator + escaped SSR partial + installed renderer, no project DB. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawnSync}=require('node:child_process'),{chromium}=require('playwright'),sharp=require('sharp');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'docs/qa/halloween-release-20261031');
const python=process.env.PYTHON_EXE||'py';
const fixture=spawnSync(python,[...(process.env.PYTHON_EXE?[]:['-3.14']),'home/js_tests/halloween_ssr_fixture.py'],{cwd:root,encoding:'utf8',timeout:60000,windowsHide:true});
assert.equal(fixture.status,0,fixture.stderr);const data=JSON.parse(fixture.stdout);
const source=JSON.parse(fs.readFileSync(path.join(root,'docs/cosmetics/halloween-fire-textured.json'),'utf8'));
const installed=JSON.parse(fs.readFileSync(path.join(root,'home/static/cosmetics/efeito-vigilia-das-lanternas.json'),'utf8'));
assert.deepEqual(installed,source);assert.equal(data.package.banner.length,8);
const report={status:'running',errors:[],viewports:[],approvedPackageIdentical:true,productionDatabaseUsed:false};
const face='#preview-banner .cosmetic-atlas--rig:not(.cosmetic-atlas--ambient)>img';
const fire='#preview-banner img[src*="vigilia-jack-fire-textured-v32.webp"]';
async function run(){
 fs.mkdirSync(out,{recursive:true});const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage();page.on('pageerror',e=>report.errors.push(e.message));
  page.on('requestfailed',r=>report.errors.push(r.url()+': '+r.failure()?.errorText));
  await page.route('https://cosmetics.test/**',async route=>{
   const pathname=new URL(route.request().url()).pathname;
   if(pathname==='/favicon.ico')return route.fulfill({status:204,body:''});
   if(pathname==='/')return route.fulfill({contentType:'text/html',body:'<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/css/components/cosmetic-presentation.css"><style>body{margin:16px;background:#151818}#preview-banner{position:relative;overflow:hidden;width:min(100%,1080px);height:241px}@media(max-width:600px){#preview-banner{height:201px}}</style><main id="preview-root"><div id="preview-banner" class="public-profile-banner">'+data.html+'</div></main><script src="/static/cosmetics/renderer.js"></script><script>CosmeticRenderer.mount(document)</script>'});
   const file=path.resolve(root,'home','.'+pathname);assert(file.startsWith(path.join(root,'home/static')+path.sep));
   assert(fs.existsSync(file),file);await route.fulfill({path:file});
  });
  const ready=()=>page.waitForFunction(()=>[...document.images].every(i=>i.complete&&i.naturalWidth)&&document.querySelector('#preview-banner .cosmetic-atlas--rig:not(.cosmetic-atlas--ambient)>img')?._cosmeticSequenceGroup?.children.length===6);
  const freeze=time=>page.evaluate(async t=>{
   document.getElementById('preview-root').classList.add('preview-paused');await document.fonts.ready;
   await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
   document.getAnimations().forEach(a=>{a.pause();a.currentTime=t*1000;});await new Promise(requestAnimationFrame);
  },time);
  for(const width of [390,1440]){
   await page.setViewportSize({width,height:800});await page.emulateMedia({reducedMotion:'no-preference'});
   await page.goto('https://cosmetics.test/');await ready();
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.equal(await page.locator('#preview-banner img[src*="wax-"]').count(),3);
   assert.equal(await page.locator('#preview-banner img[src*="flame-twelve"]').count(),6);
   assert.equal(await page.locator(fire).count(),1);
   assert(await page.locator(fire).evaluate(i=>{
    const layers=i.closest('[data-cosmetic-layers]');
    const face=layers.querySelector('.cosmetic-atlas--rig:not(.cosmetic-atlas--ambient)>img');
    return !!(i.compareDocumentPosition(face)&Node.DOCUMENT_POSITION_FOLLOWING);
   }),'Auxiliary fire must paint behind the face');
   assert.equal(await page.locator(face).evaluate(i=>i._cosmeticSequenceGroup.children.length),6);
   assert(await page.locator('img[data-cosmetic-mask],.cosmetic-atlas--masked').count());
   for(const [name,time] of [['entry',1.15],['gaze',3.7],['eyes-exit',7.7],['smile-exit',8.9]]){
    await freeze(time);await page.locator('#preview-banner').screenshot({path:path.join(out,`${width}-${name}.png`)});
   }
   await freeze(2.5);
   const sample=await sharp(await page.locator('#preview-banner').screenshot()).removeAlpha().raw().toBuffer({resolveWithObject:true});
   let firePixels=0;for(let i=0;i<sample.data.length;i+=sample.info.channels)if(sample.data[i]>120&&sample.data[i]>sample.data[i+1]*1.3&&sample.data[i+1]>25)firePixels++;
   assert(firePixels>300,'The parsed SSR output must paint visible fire');
   for(const time of [0,2.5,8.2,10,15.99]){
    await freeze(time);assert(Number(await page.locator(fire).evaluate(i=>getComputedStyle(i.parentElement).opacity))<1e-6);
   }
   await page.emulateMedia({reducedMotion:'reduce'});assert(!(await page.locator(face).isVisible()));assert(!(await page.locator(fire).isVisible()));
   report.viewports.push({width,serverRendererParity:true,noOverflow:true,noBrokenImages:true,reducedMotion:true,coreParts:6,candles:[1,2,3],firePixels});
  }
  await page.emulateMedia({reducedMotion:'no-preference'});await page.goto('https://cosmetics.test/');await ready();
  await page.locator(face).evaluate(i=>i.dispatchEvent(new Event('error')));
  assert.equal(await page.locator('.cosmetic-sequence-shade').count(),0,'Broken face removes dark backdrop');
  assert.equal(await page.locator('#preview-banner img[src*="flame-twelve"]').count(),6,'Unrelated candle rigs survive');
  assert.deepEqual(report.errors,[]);report.status='passed';console.log(JSON.stringify(report));
 }finally{await browser.close();}
}
run().catch(e=>{report.status='failed';report.failure=e.stack;console.error(e);process.exitCode=1;})
 .finally(()=>{fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify(report,null,2)+'\n');});
