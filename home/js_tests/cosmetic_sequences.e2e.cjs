/* Real SSR/live rigs and sampled motion. No server account or database. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url'),{spawnSync}=require('node:child_process');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'docs/qa/20261029-halloween-candelabra');
const fixture=spawnSync('py',['-3.14','-c',`
import json
from django.conf import settings
settings.configure(SECRET_KEY='rig-test',STATIC_URL='/static/',INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','home'],TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','APP_DIRS':True}])
import django
django.setup()
from home.cosmetic_packages import load_package
from django.template.loader import get_template
pack=load_package('efeito','vigilia-das-lanternas')
assert pack
print(json.dumps({'package':pack,'html':get_template('home/partials/_cosmetic_preview.html').render({'layers':pack['banner'],'slot':'banner'})}))
`],{cwd:root,encoding:'utf8',timeout:60000});
assert.equal(fixture.status,0,fixture.stderr);
const data=JSON.parse(fixture.stdout),base=pathToFileURL(path.join(root,'home/static/cosmetics')).href+'/';
const ssrHTML=data.html.replaceAll('/static/cosmetics/',base);
const faceSelector='#preview-banner .cosmetic-atlas--rig:not(.cosmetic-atlas--ambient)';
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),errors=[],phases=[];
 try{
  const page=await browser.newPage();page.on('pageerror',e=>errors.push(e.message));
  const settle=()=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  async function seekFace(seconds){
   await page.locator(faceSelector+'>img').evaluate((image,time)=>{
    function seek(g){g.animations.forEach(a=>{a.pause();a.currentTime=time*1000;});g.children.forEach(seek);}seek(image._cosmeticSequenceGroup);
   },seconds);await settle();
   return page.locator(faceSelector).evaluate(n=>({opacity:Number(getComputedStyle(n).opacity),
    shade:Number(getComputedStyle(n.closest('[data-cosmetic-layers]').querySelector('.cosmetic-sequence-shade')).opacity),
    pupils:[...n.querySelectorAll('.cosmetic-part>.cosmetic-atlas')].map(p=>parseFloat(getComputedStyle(p).translate))}));
  }
  for(const width of [390,1440]){
   await page.setViewportSize({width,height:1000});
   await page.goto(pathToFileURL(path.join(root,'docs/cosmetics/20261029-halloween.html')).href);
   await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(250);
   assert.equal(await page.locator('#preview-banner img[src*="candlestick-"]').count(),3);
   assert.equal(await page.locator('#preview-banner img[src*="flame-twelve"]').count(),6);
   assert.equal(await page.locator('#preview-banner img[src*="jack-pupil"]').count(),2);
   assert(await page.locator('img').evaluateAll(nodes=>nodes.every(n=>n.complete&&n.naturalWidth>0)));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   for(const [name,time,visible] of [['absent',0,false],['front',2.52,true],['left',4.68,true],['right',7.56,true],['gone',13,false]]){
    const state=await seekFace(time);assert(visible?state.opacity>.9:state.opacity<.01,name);
    assert(visible?state.shade>.7:state.shade<.01,name+' shade');
    if(name==='front')assert(state.pupils.every(x=>Math.abs(x)<.1));
    if(name==='left')assert(state.pupils.every(x=>x<-59));
    if(name==='right')assert(state.pupils.every(x=>x>59));
    await page.locator('#preview-banner').screenshot({path:path.join(out,`${width}-${name}.png`)});phases.push({width,name,...state});
   }
   await seekFace(2.52);await page.screenshot({path:path.join(out,`${width}-full.png`),fullPage:true});
  }
  const flow=await page.locator(faceSelector+' .cosmetic-part img').first().evaluate(image=>{
   const values=[],a=image._cosmeticSequenceGroup.animations[0];a.pause();
   for(let i=0;i<=240;i++){a.currentTime=i*18000/240;values.push(parseFloat(getComputedStyle(image.parentElement).translate));}
   return {maxStep:Math.max(...values.slice(1).map((x,i)=>Math.abs(x-values[i]))),range:Math.max(...values)-Math.min(...values),samples:values.length};
  });assert(flow.maxStep<6);assert(flow.range>119);
  const drift=await page.locator('#preview-banner img[src*="candlestick-"]').evaluateAll(images=>images.map(image=>{
   const g=image._cosmeticSequenceGroup,d=g.animations[0].effect.getTiming().duration,samples=[];
   for(let i=0;i<5;i++){g.animations.forEach(a=>{a.pause();a.currentTime=i*d/4;});samples.push(getComputedStyle(g.viewport).translate);}
   return {samples,imageX:new DOMMatrixReadOnly(getComputedStyle(image).transform).m41};
  }));drift.forEach(d=>{assert(new Set(d.samples).size>=4);assert.equal(d.imageX,0);});
  const flame=page.locator('#preview-banner img[src*="flame-twelve"]').first(),flameStates=[];
  for(let frame=0;frame<12;frame++){
   await flame.evaluate((image,f)=>{const g=image._cosmeticSequenceGroup,t=g.animations[0].effect.getTiming();g.animations.forEach(a=>{a.pause();a.currentTime=t.delay+t.duration*(f+.2)/12;});},frame);await settle();
   const geometry=await flame.evaluate(image=>{const m=new DOMMatrixReadOnly(getComputedStyle(image).transform),s=getComputedStyle(image.parentElement);return{x:m.m41,y:m.m42,w:parseFloat(s.width),h:parseFloat(s.height)};});
   assert(Math.abs(geometry.x+(frame%4)*geometry.w)<.1);assert(Math.abs(geometry.y+Math.floor(frame/4)*geometry.h)<.1);flameStates.push({frame,...geometry});
  }
  await page.locator('#preview-banner').evaluate((banner,html)=>{banner.querySelectorAll('[data-cosmetic-layers]').forEach(n=>n.remove());banner.insertAdjacentHTML('beforeend',html);window.CosmeticRenderer.mount(document);},ssrHTML);
  await page.waitForTimeout(250);assert.equal(await page.locator('#preview-banner img[src*="flame-twelve"]').count(),6);
  assert((await seekFace(4.68)).pupils.every(x=>x<-59));
  const timelines='#preview-banner [data-cosmetic-layers]';
  await page.locator('#preview-banner').evaluate(n=>n.style.transform='translateY(-3000px)');await page.waitForTimeout(200);
  assert(await page.locator(timelines).evaluate(n=>n._cosmeticSequences.every(a=>a.playState==='paused')));
  await page.locator('#preview-banner').evaluate(n=>n.style.transform='');await page.waitForTimeout(200);
  assert(await page.locator(timelines).evaluate(n=>n._cosmeticSequences.every(a=>a.playState==='running')));
  await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator(faceSelector).evaluate(n=>getComputedStyle(n).display),'none');
  assert(await page.locator('#preview-banner img[src*="candlestick-"]').evaluateAll(nodes=>nodes.every(n=>getComputedStyle(n.parentElement).display!=='none')));
  assert(await page.locator(timelines).evaluate(n=>n._cosmeticSequences.every(a=>a.playState==='paused')));
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.locator(faceSelector+'>img').evaluate(n=>n.dispatchEvent(new Event('error')));
  assert.equal(await page.locator(faceSelector+',.cosmetic-sequence-shade').count(),0);assert.equal(await page.locator('#preview-banner img[src*="jack-pupil"]').count(),0);
  assert.equal(await page.locator(timelines).evaluate(n=>n._cosmeticSequences.length),18);
  await page.locator('#preview-banner img[src*="candlestick-one"]').evaluate(n=>n.dispatchEvent(new Event('error')));
  assert.equal(await page.locator('#preview-banner img[src*="flame-twelve"]').count(),5);assert.equal(await page.locator(timelines).evaluate(n=>n._cosmeticSequences.length),14);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify({phases,flow,drift,flameStates,candleCounts:[1,2,3],gazeKeyPoses:24,continuousGaze:true,serverParity:true,reducedMotion:true,offscreenPause:true,parentFailureCleanup:true,errors},null,2));
  console.log('PASS: candle support rigs 1/2/3, 12 flame poses, 24 gaze keyposes, sampled fluency, SSR/live, pause, reduced motion, descendant cleanup');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
