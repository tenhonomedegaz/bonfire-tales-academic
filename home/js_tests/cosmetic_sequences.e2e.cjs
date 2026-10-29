/* Real server partial + live renderer: deterministic timeline phases, no database. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {spawnSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '../..');
const evidence = path.join(root, 'docs/qa/20261029-halloween-apparition');
const fixture = spawnSync('py', ['-3.14', '-c', `
import json
from django.conf import settings
settings.configure(SECRET_KEY='static-sequence-test',STATIC_URL='/static/',INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','home'],TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','APP_DIRS':True}])
import django
django.setup()
from home.cosmetic_packages import load_package
from django.template.loader import get_template
pack=load_package('efeito','vigilia-das-lanternas')
print(json.dumps({'package':pack,'html':get_template('home/partials/_cosmetic_preview.html').render({'layers':pack['banner'],'slot':'banner'})}))
`], {cwd:root,encoding:'utf8',timeout:60000});
assert.equal(fixture.status,0,fixture.stderr);
const data=JSON.parse(fixture.stdout);
const base=pathToFileURL(path.join(root,'home/static/cosmetics')).href+'/';
const serverHTML=data.html.replaceAll('/static/cosmetics/',base);
fs.mkdirSync(evidence,{recursive:true});
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const errors=[];
  try{
    const page=await browser.newPage();
    page.on('pageerror',e=>errors.push(e.message));
    async function seek(seconds){
      await page.locator('#preview-banner [data-cosmetic-layers]').evaluate((layer,time)=>{
        for(const animation of layer._cosmeticSequences){animation.pause();animation.currentTime=time*1000;}
      },seconds);
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      return page.locator('#preview-banner').evaluate(banner=>{
        const atlas=banner.querySelector('.cosmetic-atlas');
        return {opacity:Number(getComputedStyle(atlas).opacity),
          shade:Number(getComputedStyle(banner.querySelector('.cosmetic-sequence-shade')).opacity),
          x:new DOMMatrixReadOnly(getComputedStyle(atlas.querySelector('img')).transform).m41,
          width:atlas.getBoundingClientRect().width,
          count:banner.querySelector('[data-cosmetic-layers]')._cosmeticSequences.length};
      });
    }
    const phaseResults=[];
    for(const width of [390,1440]){
      await page.setViewportSize({width,height:1000});
      await page.goto(pathToFileURL(path.join(root,'docs/cosmetics/20261029-halloween.html')).href);
      await page.evaluate(()=>document.fonts.ready);
      await page.waitForTimeout(250);
      assert.equal(await page.locator('.cosmetic-atlas').count(),1);
      assert.equal(await page.locator('#preview-banner img[src*="floating-candle"]').count(),3);
      assert(await page.locator('img').evaluateAll(nodes=>nodes.every(n=>n.complete&&n.naturalWidth>0)));
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      for(const [name,time,frame,visible] of [['absent',0,0,false],['front',3.5,0,true],['left',5.2,1,true],['right',7.5,2,true],['gone',13,0,false]]){
        const state=await seek(time);
        assert.equal(state.count,3);
        assert(visible?state.opacity>.9:state.opacity<.01,name+' opacity');
        assert(visible?state.shade>.7:state.shade<.01,name+' shade');
        assert(Math.abs(state.x+frame*state.width)<.1,name+' frame alignment');
        await page.locator('#preview-banner').screenshot({path:path.join(evidence,`${width}-${name}.png`)});
        phaseResults.push({width,name,...state});
      }
      await seek(3.5);
      await page.screenshot({path:path.join(evidence,`${width}-full.png`),fullPage:true});
    }
    // The server-rendered path must initialize the exact same choreography.
    await page.locator('#preview-banner').evaluate((banner,html)=>{
      banner.querySelectorAll('[data-cosmetic-layers]').forEach(n=>n.remove());
      banner.insertAdjacentHTML('beforeend',html);
      window.CosmeticRenderer.mount(document);
    },serverHTML);
    await page.waitForTimeout(250);
    assert.equal(await page.locator('img[data-cosmetic-sequence]').count(),0);
    const ssr=await seek(5.2);
    assert(Math.abs(ssr.x+ssr.width)<.1);
    assert(ssr.shade>.7);
    // Offscreen and hidden tabs pause animation instead of consuming cycles.
    await page.locator('#preview-banner').evaluate(n=>{n.style.transform='translateY(-3000px)';});
    await page.waitForTimeout(200);
    assert(await page.locator('#preview-banner [data-cosmetic-layers]').evaluate(n=>n._cosmeticSequences.every(a=>a.playState==='paused')));
    await page.locator('#preview-banner').evaluate(n=>{n.style.transform='';});
    await page.waitForTimeout(200);
    assert(await page.locator('#preview-banner [data-cosmetic-layers]').evaluate(n=>n._cosmeticSequences.every(a=>a.playState==='running')));
    await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});
    assert(await page.locator('#preview-banner [data-cosmetic-layers]').evaluate(n=>n._cosmeticSequences.every(a=>a.playState==='paused')));
    await page.evaluate(()=>{delete document.hidden;document.dispatchEvent(new Event('visibilitychange'));});
    await page.emulateMedia({reducedMotion:'reduce'});
    assert.equal(await page.locator('.cosmetic-atlas').evaluate(n=>getComputedStyle(n).display),'none');
    assert.equal(await page.locator('.cosmetic-sequence-shade').evaluate(n=>getComputedStyle(n).display),'none');
    assert(await page.locator('#preview-banner [data-cosmetic-layers]').evaluate(n=>n._cosmeticSequences.every(a=>a.playState==='paused')));
    await page.emulateMedia({reducedMotion:'no-preference'});
    // Failed face media must not leave a darkening backdrop running by itself.
    await page.locator('.cosmetic-atlas-image').evaluate(n=>n.dispatchEvent(new Event('error')));
    assert.equal(await page.locator('.cosmetic-atlas,.cosmetic-sequence-shade').count(),0);
    assert.equal(await page.locator('#preview-banner [data-cosmetic-layers]').evaluate(n=>n._cosmeticSequences.length),0);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(evidence,'checks.json'),JSON.stringify({phases:phaseResults,serverParity:true,offscreenPause:true,hiddenPause:true,reducedMotion:true,failedAssetCleanup:true,errors},null,2));
    console.log('PASS: gaze phases, synchronized darkening, desktop/mobile, server parity, pauses and asset failure cleanup');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
