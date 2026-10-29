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
corners_raw = layout_manifest()
corners_raw['overlay'] = True
left = dict(corners_raw['layers'][0], motion='none', opacity=0.7, pivot={'x':0, 'y':100}, placement={'x':0, 'y':100, 'width':30}, mobile={'x':0, 'y':100, 'width':40})
left.pop('motion_params')
right = dict(left, pivot={'x':100, 'y':100}, placement={'x':100, 'y':100, 'width':30}, mobile={'x':100, 'y':100, 'width':40})
corners_raw['layers'] = [left, right]
corners = parse_layout(corners_raw)
legacy_raw = dict(corners_raw, overlay=False, layers=[base])
legacy = parse_layout(legacy_raw)
template = get_template('home/partials/_cosmetic_preview.html')
def html(pack):
  return template.render({'layers': pack['banner'], 'slot':'banner'})
print(json.dumps({'package': package, 'html': html(package), 'corners': corners, 'corners_html': html(corners), 'legacy': legacy, 'legacy_html': html(legacy)}))
`], { cwd: root, encoding: 'utf8', timeout: 60000 });
assert.equal(fixture.status, 0, fixture.stderr);
const data = JSON.parse(fixture.stdout);
const asset = fs.readFileSync(path.join(root, 'home/static/cosmetics/arcane-banner.svg'));
const imageUrl = 'data:image/svg+xml;base64,' + asset.toString('base64');
for (const key of ['html', 'corners_html', 'legacy_html']) data[key] = data[key].replaceAll('/static/cosmetics/arcane-banner.svg', imageUrl);
for (const pack of [data.package, data.corners, data.legacy]) {
  for (const layer of pack.banner) layer.url = layer.fallback = imageUrl;
}
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
    const overlayPage = await browser.newPage({ viewport: { width: 1200, height: 900 } });
    await overlayPage.setContent(`<style>${css}
      body{margin:12px;background:#17222a;color:white}
      .stage{position:relative;width:min(800px,100%);height:160px;overflow:hidden;margin-bottom:12px;background:repeating-linear-gradient(90deg,#174b48 0 30px,#a07b48 30px 60px)}
      </style><div id="overlay-server" class="stage cosmetic-has-banner">${data.corners_html}</div>
      <div id="overlay-dynamic" class="stage cosmetic-has-banner"></div>
      <div class="ficha-header"><div id="overlay-sheet" class="stage cosmetic-has-banner">${data.corners_html}</div>
      <div id="overlay-sheet-plain" class="stage">${data.corners_html}</div>
      <div id="legacy-sheet" class="stage">${data.legacy_html}</div></div>
      <div id="legacy-own-banner" class="stage cosmetic-has-banner">${data.legacy_html}</div>`);
    await overlayPage.addScriptTag({ content: renderer });
    await overlayPage.evaluate(pack => window.CosmeticRenderer.render(document.getElementById('overlay-dynamic'), 'banner', [pack]), data.corners);
    await overlayPage.locator('img').evaluateAll(images => Promise.all(images.map(image => image.decode())));
    for (const width of [1200, 390]) {
      await overlayPage.setViewportSize({ width, height: 1100 });
      const result = await overlayPage.evaluate(() => {
        const stages = ['overlay-server', 'overlay-dynamic', 'overlay-sheet', 'overlay-sheet-plain'].map(id => {
          const stage = document.getElementById(id), bounds = stage.getBoundingClientRect();
          const layer = stage.querySelector('[data-cosmetic-layers]'), style = getComputedStyle(layer);
          const positions = [...stage.querySelectorAll('.cosmetic-positioned')].map(node => {
            const box = node.getBoundingClientRect(), img = node.querySelector('img').getBoundingClientRect();
            return { left: box.left - bounds.left, right: bounds.right - box.right, bottom: bounds.bottom - box.bottom,
              ratio: img.width / img.height, width: box.width / bounds.width };
          });
          return { opacity: style.opacity, blend: style.mixBlendMode, positions };
        });
        return { stages, oldOwn: getComputedStyle(document.querySelector('#legacy-own-banner [data-cosmetic-layers]')).opacity,
          oldSheet: getComputedStyle(document.querySelector('#legacy-sheet [data-cosmetic-layers]')).opacity,
          background: getComputedStyle(document.getElementById('overlay-server')).backgroundImage };
      });
      for (const stage of result.stages) {
        assert.equal(stage.opacity, '1');
        assert.equal(stage.blend, 'normal');
        assert.ok(Math.abs(stage.positions[0].left) < 0.1, 'left pivot not anchored');
        assert.ok(Math.abs(stage.positions[1].right) < 0.1, 'right pivot not anchored');
        for (const box of stage.positions) {
          assert.ok(Math.abs(box.bottom) < 0.1, 'bottom pivot not anchored');
          assert.ok(Math.abs(box.ratio - 1200 / 340) < 0.01, 'corner deformed');
          assert.ok(Math.abs(box.width - (width < 600 ? 0.4 : 0.3)) < 0.01);
        }
      }
      assert.deepEqual(result.stages[0], result.stages[1], 'overlay template/JS mismatch');
      assert.equal(result.oldOwn, '0.12');
      assert.equal(result.oldSheet, '0.65');
      assert.ok(result.background.includes('repeating-linear-gradient'), 'custom background changed');
    }
    await overlayPage.emulateMedia({ reducedMotion: 'reduce' });
    assert.notEqual(await overlayPage.locator('#overlay-dynamic .cosmetic-positioned').first().evaluate(node => getComputedStyle(node).transform), 'none');
    // Load the actual page cascade, not just the shared cosmetic stylesheet.
    const readCss = file => fs.readFileSync(path.join(root, 'home/static/css', file), 'utf8');
    const profileCss = ['pages/perfil.css', 'pages/perfil-fx.css', 'pages/profile-redesign.css'];
    const sheetCss = ['pages/ficha.css', 'pages/perfil-fx.css', 'pages/character-workflows.css'];
    const surfaces = [
      ['public-profile', 'bft-public-profile', 'public-profile-banner', 'public-profile-banner-media', profileCss, ''],
      ['profile-preview', 'bft-profile', 'public-profile-banner', 'public-profile-banner-media', profileCss, ''],
      ['profile-editor', 'bft-profile', 'profile-header profile-hero', 'profile-banner-media', profileCss, 'profile-hero-copy'],
      ['sheet', 'bft-character-sheet', 'banner-scroll', 'ficha-banner-media', sheetCss, 'ficha-title-line'],
      ['public-sheet', 'bft-public-sheet', 'ficha-header cw-public-hero', 'ficha-banner-media', sheetCss, 'cw-public-identity'],
      ['sheet-preview', 'bft-character-sheet', 'ficha-header ficha-live-preview', 'ficha-banner-media', sheetCss, 'ficha-name'],
    ];
    const stackingPage = await browser.newPage();
    const screenshots = fs.mkdtempSync(path.join(os.tmpdir(), 'bonfire-layer-layout-'));
    for (const [name, bodyClass, stageClass, mediaClass, styles, contentClass] of surfaces) {
      await stackingPage.setContent(`<style>${readCss('components/ranks.css')}${css}${styles.map(readCss).join('\n')}
        .stack-stage{width:100%;height:180px;min-height:180px;box-sizing:border-box;margin:0 0 12px}
        .stack-content{position:absolute!important;inset:0!important;margin:0!important}
        .stack-stage .cosmetic-layers{pointer-events:auto}
        </style><body class="${bodyClass}"><div class="ficha-header" id="stacking"></div></body>`);
      await stackingPage.addScriptTag({ content: renderer });
      await stackingPage.evaluate(({ stageClass, mediaClass, contentClass, data }) => {
        const root = document.getElementById('stacking');
        for (const ownBanner of [false, true]) for (const dynamic of [false, true]) for (const overlay of [false, true]) {
          const stage = document.createElement('div');
          stage.className = `stack-stage ${stageClass}${ownBanner ? ' cosmetic-has-banner' : ''}`;
          stage.dataset.ownBanner = ownBanner;
          stage.dataset.overlay = overlay;
          stage.dataset.dynamic = dynamic;
          const media = document.createElement('div');
          media.className = mediaClass;
          media.style.backgroundImage = 'url("' + data.package.banner[0].url + '")';
          if (ownBanner && !dynamic) stage.appendChild(media);
          if (!dynamic) stage.insertAdjacentHTML('beforeend', overlay ? data.corners_html : data.legacy_html);
          if (contentClass) stage.insertAdjacentHTML('beforeend', `<div class="stack-content ${contentClass}">Identity</div>`);
          stage.insertAdjacentHTML('beforeend', `<div class="cosmetic-layers cosmetic-layers--ornament"></div>
            <div class="banner-character-avatar profile-avatar-wrapper rank-portrait" style="width:40px;height:40px">
              <img src="${data.package.banner[0].url}" alt=""><span class="rank-portrait-frame"><img src="${data.package.banner[0].url}" alt=""></span>
            </div>`);
          root.appendChild(stage);
          if (dynamic) window.CosmeticRenderer.render(stage, 'banner', [overlay ? data.corners : data.legacy]);
          // Uploaded preview banners can be appended after cosmetic rendering.
          if (ownBanner && dynamic) stage.appendChild(media);
        }
      }, { stageClass, mediaClass, contentClass, data });
      for (const width of [1200, 390]) {
        await stackingPage.setViewportSize({ width, height: 1800 });
        const results = await stackingPage.locator('.stack-stage').evaluateAll(stages => stages.map(stage => {
          const layer = stage.querySelector('.cosmetic-layers--banner');
          const media = stage.querySelector('[class$="banner-media"]');
          const image = layer.querySelector('img').getBoundingClientRect();
          const paint = document.elementsFromPoint(image.x + image.width / 2, image.y + image.height / 2);
          const content = stage.querySelector('.stack-content');
          const portrait = stage.querySelector('.rank-portrait');
          return { own: stage.dataset.ownBanner === 'true', overlay: stage.dataset.overlay === 'true',
            dynamic: stage.dataset.dynamic, layerZ: Number(getComputedStyle(layer).zIndex),
            mediaZ: media && Number(getComputedStyle(media).zIndex),
            aboveMedia: !media || paint.indexOf(layer) < paint.indexOf(media),
            aboveContent: content && paint.indexOf(layer) < paint.indexOf(content),
            ornamentZ: Number(getComputedStyle(stage.querySelector('.cosmetic-layers--ornament')).zIndex),
            rankZ: Number(getComputedStyle(portrait.querySelector('.rank-portrait-frame')).zIndex),
            rankIsolation: getComputedStyle(portrait).isolation,
            position: getComputedStyle(layer).position };
        }));
        for (const result of results) {
          const label = `${name}/${width}/${JSON.stringify(result)}`;
          assert.equal(result.position, 'absolute', label);
          if (result.overlay && result.own) {
            assert.ok(result.layerZ > result.mediaZ, 'overlay must be above banner: ' + label);
            assert.equal(result.aboveMedia, true, 'banner covers overlay: ' + label);
          }
          if (result.overlay && contentClass) assert.equal(result.aboveContent, false, 'overlay covers identity: ' + label);
          if (!result.overlay) assert.equal(result.layerZ, 0, 'legacy stack changed: ' + label);
          assert.equal(result.ornamentZ, 2, 'ornament stack changed: ' + label);
          assert.equal(result.rankZ, 4, 'rank frame stack changed: ' + label);
          assert.equal(result.rankIsolation, 'isolate', 'rank isolation changed: ' + label);
        }
        await stackingPage.screenshot({ path: path.join(screenshots, `stacking-${name}-${width}.png`) });
      }
    }
    for (const width of [1200, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await page.screenshot({ path: path.join(screenshots, `layers-${width}.png`) });
      await overlayPage.setViewportSize({ width, height: 1100 });
      await overlayPage.screenshot({ path: path.join(screenshots, `overlay-pivots-${width}.png`) });
    }
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ passed: ['server/dynamic parity', 'desktop/mobile ratio and placement', 'legacy cover', 'horizontal travel and opacity fade', 'static moon', 'offscreen pause', 'hidden-tab pause/resume', 'reduced-motion centering', 'overlay above own banner and sheet', 'bottom corner pivots desktop/mobile', 'legacy attenuation preserved', 'real CSS stacking: 6 surfaces, desktop/mobile, own/no banner, server/dynamic, overlay/legacy'], motion, screenshots }));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
