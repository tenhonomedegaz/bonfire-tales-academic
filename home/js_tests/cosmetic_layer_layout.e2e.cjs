/* Real server markup vs dynamic renderer, with no server, account or database. */
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const python = process.env.COSMETIC_PYTHON || (process.platform === 'win32' ? 'py' : 'python3');
const fixture = spawnSync(python, [
  ...(process.platform === 'win32' && !process.env.COSMETIC_PYTHON ? ['-3.14'] : []), '-c', `
import json
from pathlib import Path
from django.conf import settings
settings.configure(SECRET_KEY='static-layout-test', STATIC_URL='/static/', BASE_DIR=Path.cwd(), INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','home'], TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','APP_DIRS':True}])
import django
django.setup()
from home.test_cosmetic_layer_layout import layout_manifest, parse_layout
from django.template.loader import get_template
raw = layout_manifest()
cloud = raw['layers'][0]
cloud['opacity'] = 0.55
base = {key: value for key, value in cloud.items() if key not in ('placement','mobile','motion_params','opacity')}
base['motion'] = 'none'
moon = dict(cloud, motion='none', opacity=0.7)
moon.pop('motion_params')
raw['layers'] = [base, moon, cloud]
package = parse_layout(raw)
print(json.dumps({'package': package, 'html': get_template('home/partials/_cosmetic_preview.html').render({'layers': package['banner'], 'slot': 'banner'})}))
`], { cwd: root, encoding: 'utf8', timeout: 60000 });
assert.equal(fixture.status, 0, fixture.stderr);
const data = JSON.parse(fixture.stdout);
const asset = fs.readFileSync(path.join(root, 'home/static/cosmetics/arcane-banner.svg'));
const imageUrl = 'data:image/svg+xml;base64,' + asset.toString('base64');
data.html = data.html.replaceAll('/static/cosmetics/arcane-banner.svg', imageUrl);
for (const layer of data.package.banner) layer.url = layer.fallback = imageUrl;
const css = fs.readFileSync(path.join(root, 'home/static/css/components/cosmetic-presentation.css'), 'utf8');
const renderer = fs.readFileSync(path.join(root, 'home/static/cosmetics/renderer.js'), 'utf8');

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.COSMETIC_CHANNEL ? { channel: process.env.COSMETIC_CHANNEL } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1200, height: 900 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent(`<style>${css}
      body{margin:12px;background:#17222a;color:white;font:16px Arial}
      .stage{position:relative;width:min(800px,100%);height:240px;margin-bottom:20px;overflow:hidden;background:#274b4a}
      #offscreen{position:absolute;top:4000px}
      </style><h2>Server</h2><div class="stage" id="server">${data.html}</div>
      <h2>Dynamic</h2><div class="stage" id="dynamic"></div><div class="stage" id="offscreen"></div>`);
    await page.addScriptTag({ content: renderer });
    await page.evaluate(pack => {
      for (const id of ['dynamic', 'offscreen']) window.CosmeticRenderer.render(document.getElementById(id), 'banner', [pack]);
    }, data.package);
    await page.waitForFunction(() => document.querySelector('#server [data-cosmetic-layers]').classList.contains('is-visible'));
    await page.locator('img').evaluateAll(images => Promise.all(images.map(image => image.decode())));

    for (const width of [1200, 390]) {
      await page.setViewportSize({ width, height: 900 });
      const check = await page.evaluate(() => {
        const layout = id => [...document.querySelectorAll('#' + id + ' .cosmetic-positioned')].map(node => {
          const style = getComputedStyle(node), image = node.querySelector('img'), imageStyle = getComputedStyle(image);
          return [style.left, style.top, style.width, imageStyle.width, imageStyle.height, imageStyle.animationName, imageStyle.animationDuration, imageStyle.animationDelay, imageStyle.getPropertyValue('--cosmetic-opacity')];
        });
        const stage = document.getElementById('server').getBoundingClientRect();
        const positioned = document.querySelector('#server .cosmetic-positioned');
        const s = getComputedStyle(positioned);
        const img = positioned.querySelector('img').getBoundingClientRect();
        return { server: layout('server'), dynamic: layout('dynamic'), ratio: img.width / img.height,
          width: parseFloat(s.width) / stage.width, x: parseFloat(s.left) / stage.width, y: parseFloat(s.top) / stage.height,
          overflow: document.documentElement.scrollWidth > innerWidth,
          base: getComputedStyle(document.querySelector('#server .cosmetic-layer--none')).objectFit };
      });
      assert.deepEqual(check.server, check.dynamic, 'server/dynamic layout mismatch');
      assert.ok(Math.abs(check.ratio - 1200 / 340) < 0.01, 'deformed image');
      assert.ok(Math.abs(check.width - (width < 600 ? 1.8 : 1.2)) < 0.01);
      assert.ok(Math.abs(check.x - (width < 600 ? 0.55 : 0.45)) < 0.01);
      assert.ok(Math.abs(check.y - (width < 600 ? 0.25 : 0.30)) < 0.01);
      assert.equal(check.overflow, false);
      assert.equal(check.base, 'cover');
    }

    const motion = await page.evaluate(() => {
      const image = document.querySelector('#server .cosmetic-layer--drift');
      const animation = image.getAnimations()[0];
      const state = getComputedStyle(image).animationPlayState;
      animation.pause();
      const sample = time => { animation.currentTime = time; const s = getComputedStyle(image); return { x: new DOMMatrix(s.transform).m41, opacity: Number(s.opacity) }; };
      return { state, a: sample(45000), b: sample(75000), edge: sample(30000),
        offscreen: getComputedStyle(document.querySelector('#offscreen .cosmetic-layer--drift')).animationPlayState,
        moon: document.querySelector('#server .cosmetic-positioned .cosmetic-layer--none').getAnimations().length };
    });
    assert.equal(motion.state, 'running');
    assert.ok(motion.b.x - motion.a.x > 100, 'horizontal drift not visible');
    assert.equal(motion.a.opacity, 0.55);
    assert.equal(motion.b.opacity, 0.55);
    assert.equal(motion.edge.opacity, 0);
    assert.equal(motion.offscreen, 'paused');
    assert.equal(motion.moon, 0);

    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', { configurable: true, value: true });
      document.dispatchEvent(new Event('visibilitychange'));
    });
    assert.equal(await page.locator('#dynamic .cosmetic-layer--drift').evaluate(node => getComputedStyle(node).animationPlayState), 'paused');
    await page.evaluate(() => { delete document.hidden; document.dispatchEvent(new Event('visibilitychange')); });
    assert.equal(await page.locator('#dynamic .cosmetic-layer--drift').evaluate(node => getComputedStyle(node).animationPlayState), 'running');
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const reduced = await page.locator('#dynamic .cosmetic-layer--drift').evaluate(node => ({
      animation: getComputedStyle(node).animationName, opacity: getComputedStyle(node).opacity,
      imageTransform: getComputedStyle(node).transform, wrapperTransform: getComputedStyle(node.parentElement).transform,
    }));
    assert.equal(reduced.animation, 'none');
    assert.equal(reduced.imageTransform, 'none');
    assert.equal(reduced.opacity, '0.55');
    assert.notEqual(reduced.wrapperTransform, 'none', 'reduced motion lost centering');
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    const screenshots = fs.mkdtempSync(path.join(os.tmpdir(), 'bonfire-layer-layout-'));
    for (const width of [1200, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await page.screenshot({ path: path.join(screenshots, `layers-${width}.png`) });
    }
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ passed: ['server/dynamic parity', 'desktop/mobile ratio and placement', 'legacy cover', 'horizontal travel and opacity fade', 'static moon', 'offscreen pause', 'hidden-tab pause/resume', 'reduced-motion centering'], motion, screenshots }));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
