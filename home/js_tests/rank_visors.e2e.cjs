/* Real packaged rank artwork: stable base, independent plates and masked hover. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '../..');
const out = process.env.RANK_QA_OUT || path.join(root, 'docs/qa/rank-visors-20261102');
const ranks = ['obsidiana','ametista','topazio','esmeralda','ambar','rubi','diamante'];

(async () => {
  fs.mkdirSync(out, {recursive:true});
  const browser = await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL || 'msedge',headless:true});
  const report = {ranks, checks:[], errors:[]};
  try {
    const page = await browser.newPage();
    page.on('pageerror', e => report.errors.push(e.message));
    page.on('requestfailed', r => report.errors.push(r.url()));
    for (const width of [390,768,1440]) {
      await page.setViewportSize({width,height:1000});
      await page.goto(pathToFileURL(path.join(root,'docs/cosmetics/20261102-rank-metal.html')).href);
      await page.waitForFunction(() => document.querySelectorAll('[data-rank]').length===7);
      await page.evaluate(()=>document.querySelectorAll('img').forEach(i=>i.loading='eager'));
      await page.waitForFunction(() => [...document.images].every(i=>i.complete && i.naturalWidth));
      await page.evaluate(()=>Promise.all([...document.images].map(i=>i.decode())));
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      for (const rank of ranks) {
        const card = page.locator('[data-rank="tema-rank-'+rank+'"]');
        const avatar = card.locator('.closed-avatar');
        const plates = avatar.locator('.cosmetic-layer--retract');
        const base = avatar.locator('.cosmetic-layers--avatar > .cosmetic-layer--none');
        await avatar.scrollIntoViewIfNeeded();
        await page.mouse.move(0,0);
        await page.evaluate(()=>document.activeElement?.blur());
        await page.waitForTimeout(700);
        assert.equal(await plates.count(),3);
        assert.equal(await avatar.locator('.cosmetic-helmet').count(),0);
        const baseBefore = await base.evaluate(e=>({html:e.outerHTML,rect:[e.offsetLeft,e.offsetTop,e.offsetWidth,e.offsetHeight],transform:getComputedStyle(e).transform,opacity:getComputedStyle(e).opacity}));
        assert.deepEqual(await plates.evaluateAll(els=>els.map(e=>getComputedStyle(e).opacity)),['1','1','1']);
        assert(await avatar.locator('.cosmetic-retract-viewport').evaluateAll(els=>els.every(e=>getComputedStyle(e).maskImage!=='none')));
        if (width===1440) await card.screenshot({path:path.join(out,rank+'-closed.png')});
        await avatar.hover();
        await page.waitForTimeout(170);
        const mid = await plates.evaluateAll(els=>els.map(e=>({transform:getComputedStyle(e).transform,opacity:Number(getComputedStyle(e).opacity)})));
        const matrices = mid.map(p=>p.transform);
        assert.equal(new Set(matrices).size,3,'Plates must have independent trajectories');
        if (width===1440) await avatar.screenshot({path:path.join(out,rank+'-opening.png')});
        await page.waitForTimeout(700);
        assert.deepEqual(await plates.evaluateAll(els=>els.map(e=>getComputedStyle(e).opacity)),['0','0','0']);
        const baseAfter = await base.evaluate(e=>({html:e.outerHTML,rect:[e.offsetLeft,e.offsetTop,e.offsetWidth,e.offsetHeight],transform:getComputedStyle(e).transform,opacity:getComputedStyle(e).opacity}));
        assert.deepEqual(baseAfter,baseBefore,'Open base must never move or crossfade');
        if (width===1440) await card.screenshot({path:path.join(out,rank+'-opened.png')});
        await page.mouse.move(0,0);
        await page.waitForTimeout(700);
        assert.deepEqual(await plates.evaluateAll(els=>els.map(e=>getComputedStyle(e).opacity)),['1','1','1']);
        await avatar.focus();
        await page.waitForTimeout(700);
        assert.deepEqual(await plates.evaluateAll(els=>els.map(e=>getComputedStyle(e).opacity)),['0','0','0']);
        await avatar.evaluate(e=>e.blur());
        report.checks.push({width,rank,baseFixed:true,independentTrajectories:true,masked:true,hover:true,keyboard:true,reversible:true});
      }
      const sample = page.locator('.closed-avatar').first();
      for (const size of [46,80,120]) {
        await sample.evaluate((e,n)=>{e.style.width=n+'px';e.style.height=n+'px';e.style.flexBasis=n+'px';},size);
        const box = await sample.boundingBox();
        assert(Math.abs(box.width/box.height-1)<.001);
        await sample.hover();await page.waitForTimeout(700);
        assert.deepEqual(await sample.locator('.cosmetic-layer--retract').evaluateAll(els=>els.map(e=>getComputedStyle(e).opacity)),['0','0','0']);
      }
      await page.emulateMedia({reducedMotion:'reduce'});
      await sample.focus();
      assert(await sample.locator('.cosmetic-layer--retract').evaluateAll(els=>els.every(e=>getComputedStyle(e).transitionDuration.split(',').every(v=>parseFloat(v)===0))));
      assert.deepEqual(await sample.locator('.cosmetic-layer--retract').evaluateAll(els=>els.map(e=>getComputedStyle(e).opacity)),['0','0','0']);
      await page.emulateMedia({reducedMotion:'no-preference'});
    }
    assert.deepEqual(report.errors,[]);
    report.passed=true;
    console.log(JSON.stringify(report));
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify(report,null,2));
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
