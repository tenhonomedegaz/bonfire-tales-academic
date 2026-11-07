/* File previews cannot fetch manifests. Keep this snapshot faithful to the real packages. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const media = path.join(root, 'home/static/cosmetics');
const snapshotPath = path.join(__dirname, 'blood-moon-preview-data.js');

function readConfig() {
  const html = fs.readFileSync(path.join(__dirname, '20261027-art-direction.html'), 'utf8');
  const opening = '<script type="application/json" id="moon-config">';
  const start = html.indexOf(opening);
  assert.notEqual(start, -1, 'Document family map is missing');
  const end = html.indexOf('</script>', start + opening.length);
  assert.notEqual(end, -1, 'Document family map is not closed');
  return JSON.parse(html.slice(start + opening.length, end));
}

function validateManifest(raw, family, roles, checkFiles = true) {
  assert.equal(raw.version, 1);
  assert.equal(raw.type, 'efeito');
  assert.equal(raw.slug + '.json', family.manifest);
  assert.equal(raw.overlay, true, family.manifest + ': overlay must be true');
  assert.ok(Array.isArray(raw.layers) && raw.layers.length > 0, family.manifest + ': no layers');
  const found = new Set();
  for (const layer of raw.layers) {
    assert.equal(layer.slot, 'banner', 'The three-theme preview requires real banner layers');
    assert.match(layer.file, /^[a-z0-9-]+\.(?:png|webp)$/);
    assert.match(layer.fallback, /^[a-z0-9-]+\.(?:png|webp)$/);
    const role = roles.find(role => layer.file.startsWith(family.family + '-' + role + '-v'));
    assert.ok(role, family.manifest + ': unsupported asset (no sky or combined foreground): ' + layer.file);
    assert.ok(layer.fallback.startsWith(family.family + '-' + role + '-v'), 'Fallback must represent the same asset role');
    assert.ok(Number.isFinite(layer.width) && layer.width > 0 && Number.isFinite(layer.height) && layer.height > 0);
    assert.ok(layer.placement, layer.file + ': missing desktop placement');
    assert.ok(layer.mobile, layer.file + ': missing mobile placement');
    if (checkFiles) {
      assert.ok(fs.existsSync(path.join(media, layer.file)), 'Missing asset: ' + layer.file);
      assert.ok(fs.existsSync(path.join(media, layer.fallback)), 'Missing fallback: ' + layer.fallback);
    }
    found.add(role);
  }
  assert.deepEqual([...found].sort(), [...roles].sort(), family.manifest + ': every asset role must be present');
}

function buildSnapshot() {
  const config = readConfig();
  assert.deepEqual(Object.keys(config.families), ['vermelha', 'negra', 'cristal']);
  const roles = Object.keys(config.roles);
  assert.equal(roles.length, 6);
  const result = {};
  for (const [key, family] of Object.entries(config.families)) {
    assert.match(family.manifest, /^efeito-lua-[a-z]+\.json$/);
    const raw = JSON.parse(fs.readFileSync(path.join(media, family.manifest), 'utf8'));
    validateManifest(raw, family, roles);
    result[key] = {
      slug: raw.slug, type: raw.type, version: raw.version, overlay: raw.overlay,
      banner: raw.layers.map(layer => ({
        ...layer, sprite: layer.sprite || 'full', anchor: layer.anchor || 'center', overlay: raw.overlay,
        url: '../../home/static/cosmetics/' + layer.file,
        fallback: '../../home/static/cosmetics/' + layer.fallback,
      })),
      ornament: [], avatar: [],
    };
  }
  return result;
}

function validateFrame(raw, family, checkFiles = true) {
  assert.equal(raw.version, 1);
  assert.equal(raw.type, 'moldura');
  assert.equal(raw.slug + '.json', family.frameManifest);
  assert.ok(['perfil', 'ambos'].includes(raw.scope));
  assert.ok(raw.overlay === undefined || typeof raw.overlay === 'boolean');
  assert.ok(Array.isArray(raw.layers) && raw.layers.length === 1, 'One calibrated frame per family');
  for (const layer of raw.layers) {
    assert.equal(layer.slot, 'avatar');
    for (const property of ['file', 'fallback']) {
      assert.ok(new RegExp('^avatar-' + family.family + '-v[1-9][0-9]*\\.(png|webp)$').test(layer[property]),
        family.frameManifest + ': unexpected avatar filename: ' + layer[property]);
      if (checkFiles) {
        const asset = path.join(media, layer[property]);
        assert.ok(fs.statSync(asset).isFile());
        assert.ok(fs.statSync(asset).size <= 4 * 1024 * 1024);
      }
    }
    assert.equal(layer.file.replace(/\.[^.]+$/, ''), layer.fallback.replace(/\.[^.]+$/, ''), 'Fallback must use the same frame version');
    for (const dimension of ['width', 'height']) {
      assert.ok(Number.isInteger(layer[dimension]) && layer[dimension] >= 32 && layer[dimension] <= 4096);
    }
    assert.ok(['center', 'left', 'right'].includes(layer.anchor || 'center'));
    assert.ok(['none', 'float', 'pulse'].includes(layer.motion || 'none'));
    assert.equal(layer.sprite || 'full', 'full');
    assert.ok(!['placement', 'mobile', 'motion_params', 'pivot'].some(key => key in layer));
    if ('opacity' in layer) assert.ok(typeof layer.opacity === 'number' && Number.isFinite(layer.opacity) && layer.opacity >= 0 && layer.opacity <= 1);
    assert.ok(layer.aperture && typeof layer.aperture === 'object');
    for (const key of ['cx', 'cy', 'diameter']) {
      const value = layer.aperture[key];
      assert.ok(typeof value === 'number' && Number.isFinite(value) && value > 0 && value < 100,
        family.frameManifest + ': invalid aperture ' + key);
    }
  }
}

function buildFrames() {
  return Object.fromEntries(Object.entries(readConfig().families).map(([key, family]) => {
    assert.equal(family.frameManifest, 'moldura-lua-' + key + '.json');
    const raw = JSON.parse(fs.readFileSync(path.join(media, family.frameManifest), 'utf8'));
    validateFrame(raw, family);
    return [key, {
      slug: raw.slug, type: raw.type, version: raw.version, overlay: raw.overlay ?? false,
      banner: [], ornament: [],
      avatar: raw.layers.map(layer => ({
        ...layer, anchor: layer.anchor || 'center', motion: layer.motion || 'none',
        sprite: layer.sprite || 'full', overlay: raw.overlay ?? false,
        aperture: Object.fromEntries(['cx', 'cy', 'diameter'].map(key => [key, layer.aperture[key]])),
        url: '../../home/static/cosmetics/' + layer.file,
        fallback: '../../home/static/cosmetics/' + layer.fallback,
      })),
    }];
  }));
}

function testFrameSchema() {
  for (const family of Object.values(readConfig().families)) {
    const layer = { slot: 'avatar', file: 'avatar-' + family.family + '-v1.webp',
      fallback: 'avatar-' + family.family + '-v1.png', width: 1024, height: 1024,
      aperture: { cx: 50, cy: 48, diameter: 60 } };
    const raw = { version: 1, type: 'moldura', slug: family.frameManifest.slice(0, -5), scope: 'ambos', layers: [layer] };
    validateFrame(raw, family, false);
    for (const patch of [{slot: 'banner'}, {file: '../avatar.png'}, {file: family.family + '-disc-v1.png'},
      {fallback: 'avatar-other-moon-v1.png'}, {aperture: null}, {width: 31}, {motion: 'drift'},
      ...['cx', 'cy', 'diameter'].flatMap(key => [0, 100, -1, NaN, Infinity, true, '50', undefined].map(value =>
        ({aperture: {...layer.aperture, [key]: value}})))]) {
      assert.throws(() => validateFrame({...raw, layers: [{...layer, ...patch}]}, family, false));
    }
  }
  console.log('Frame schema: three families, avatar filenames, scope, dimensions and aperture invalid-input tests OK.');
}

function testServerFrames(frames) {
  const { spawnSync } = require('node:child_process');
  const script = [
    'import os,json',
    'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bonfire.settings")',
    'import django; django.setup()',
    'from django.db import connection',
    'from home.cosmetic_packages import load_package',
    'def no_sql(*args, **kwargs): raise AssertionError("Preview must not access the database")',
    'with connection.execute_wrapper(no_sql):',
    ' print(json.dumps({k:load_package("moldura", "lua-"+k) for k in ["vermelha","negra","cristal"]}))',
  ].join('\n');
  const run = spawnSync(process.env.BONFIRE_PYTHON || 'python', ['-c', script], {cwd: root, encoding: 'utf8'});
  assert.equal(run.status, 0, run.stderr || run.error?.message);
  const server = JSON.parse(run.stdout);
  for (const [key, frame] of Object.entries(frames)) {
    assert.ok(server[key], key + ': load_package rejected frame');
    const expected = server[key].avatar[0];
    for (const property of ['anchor', 'motion', 'sprite', 'width', 'height', 'overlay', 'aperture', 'opacity']) {
      assert.deepEqual(frame.avatar[0][property], expected[property], key + ': server parity ' + property);
    }
    for (const property of ['url', 'fallback']) {
      assert.equal(path.posix.basename(frame.avatar[0][property]), path.posix.basename(expected[property]));
      assert.ok(frame.avatar[0][property].startsWith('../../home/static/cosmetics/'));
    }
  }
  console.log('Three frames match server load_package, including aperture; SQL forbidden.');
}

function sourceFor(snapshot, frames) {
  return '// Generated by build-moon-preview.cjs; edit the manifests, not this snapshot.\n' +
    'window.BonfireMoonPreviews = ' + JSON.stringify(snapshot, null, 2) + ';\n' +
    'window.BonfireMoonFrames = ' + JSON.stringify(frames, null, 2) + ';\n';
}

function testValidation(snapshot) {
  const config = readConfig();
  const roles = Object.keys(config.roles);
  for (const [key, pack] of Object.entries(snapshot)) {
    const raw = JSON.parse(fs.readFileSync(path.join(media, config.families[key].manifest), 'utf8'));
    assert.equal(pack.overlay, true);
    assert.equal(pack.banner.length, raw.layers.length);
    raw.layers.forEach((layer, index) => {
      for (const property of Object.keys(layer).filter(key => key !== 'fallback')) {
        assert.deepEqual(pack.banner[index][property], layer[property], 'Snapshot must preserve ' + property);
      }
    });
    assert.throws(() => validateManifest({ ...raw, overlay: false }, config.families[key], roles, false));
    assert.throws(() => validateManifest({ ...raw, layers: raw.layers.filter(layer => !layer.file.includes('foreground-left')) }, config.families[key], roles, false));
    assert.throws(() => validateManifest({ ...raw, layers: raw.layers.map((layer, i) => i ? layer : { ...layer, file: config.families[key].family + '-sky-v1.png' }) }, config.families[key], roles, false));
  }
  console.log('Three real manifests: overlay, all six roles, split foreground, source geometry and invalid-input tests OK.');
}

async function browserTest(snapshot) {
  const os = require('node:os');
  const { pathToFileURL } = require('node:url');
  const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE || 'playwright');
  const output = process.env.BONFIRE_ARTIFACT_DIR || fs.mkdtempSync(path.join(os.tmpdir(), 'bonfire-three-moons-'));
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, channel: process.env.BONFIRE_BROWSER_CHANNEL || 'msedge',
    args: ['--allow-file-access-from-files'] });
  const config = readConfig();
  try {
    for (const width of [320, 390, 768, 1280]) {
      const page = await browser.newPage({ viewport: { width, height: 940 } });
      const errors = [], network = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => {
        if (request.method() !== 'GET' || /^https?:/.test(request.url())) network.push(request.url());
      });
      await page.goto(pathToFileURL(path.join(__dirname, '20261027-art-direction.html')).href);
      assert.deepEqual(await page.evaluate(() => Object.keys(window.BonfireMoonPreviews)), Object.keys(snapshot));
      assert.equal(await page.locator('.moon-hero').count(), 3);
      assert.equal(await page.locator('.moon-hero .cosmetic-layers--overlay').count(), 3);
      assert.equal(await page.locator('[data-layer-toggle="foreground-left"]').count(), 3);
      assert.equal(await page.locator('[data-layer-toggle="foreground-right"]').count(), 3);
      assert.equal(await page.locator('[data-layer-toggle="sky"]').count(), 0);
      const alpha = await page.evaluate(async () => {
        const results = [];
        for (const [key, pack] of Object.entries(window.BonfireMoonPreviews)) {
          for (const source of new Set(pack.banner.map(layer => layer.fallback))) {
            const image = new Image(); image.src = source; await image.decode();
            const canvas = document.createElement('canvas'); canvas.width = 160; canvas.height = 160;
            const ctx = canvas.getContext('2d'); ctx.drawImage(image, 0, 0, 160, 160);
            const pixels = ctx.getImageData(0, 0, 160, 160).data;
            let transparent = 0;
            for (let i = 3; i < pixels.length; i += 4) if (pixels[i] < 8) transparent++;
            results.push({ key, source, transparent: transparent / (160 * 160) });
          }
        }
        return results;
      });
      assert.equal(alpha.length, 18, 'six transparent assets per family');
      for (const result of alpha) assert.ok(result.transparent >= .1, 'Opaque asset: ' + JSON.stringify(result));
      for (const [key, family] of Object.entries(config.families)) {
        const hero = page.locator('[data-moon-hero="' + key + '"]');
        const card = page.locator('[data-moon-card="' + key + '"]');
        const portraits = card.locator('.preview-avatar');
        assert.equal(await portraits.count(), 3);
        assert.equal(await card.locator('.has-calibrated-portrait').count(), 3);
        assert.equal(await card.locator('.preview-avatar--medium').evaluate(node => node.getBoundingClientRect().width), 120);
        assert.equal(await hero.locator('.preview-avatar').evaluate(node => node.getBoundingClientRect().width), 40);
        assert.equal(await portraits.locator('.cosmetic-layer').evaluateAll(async images => {
          await Promise.all(images.map(image => image.decode()));
          return images.every(image => image.naturalWidth > 0);
        }), true);
        const projection = await card.evaluate(async node => {
          const image = node.querySelector('.preview-avatar--medium .cosmetic-layer');
          const original = node.querySelector('[data-frame-original]');
          await original.decode();
          const rendered = image.getBoundingClientRect(), reference = original.getBoundingClientRect();
          return {ratio:rendered.width/rendered.height,intrinsic:image.naturalWidth/image.naturalHeight,
            referenceRatio:reference.width/reference.height,fit:getComputedStyle(image).objectFit,
            sizeDifference:Math.abs(rendered.width-reference.width)};
        });
        assert.equal(projection.ratio,projection.intrinsic,'Do not stretch the frame');
        assert.equal(projection.ratio,projection.referenceRatio,'Original and equipped frame must share proportions');
        assert.equal(projection.fit,'contain');
        assert.ok(projection.sizeDifference<1,'Compare the original and equipped frame at the same scale');
        const calibrated = await portraits.evaluateAll(nodes => nodes.map(node => {
          const box = node.getBoundingClientRect(), photo = node.querySelector(':scope > img').getBoundingClientRect();
          return { width: photo.width / box.width, x: (photo.x + photo.width / 2 - box.x) / box.width,
            y: (photo.y + photo.height / 2 - box.y) / box.height };
        }));
        const aperture = await page.evaluate(key => window.BonfireMoonFrames[key].avatar[0].aperture, key);
        for (const photo of calibrated) {
          assert.ok(Math.abs(photo.width - aperture.diameter * .0132) < .005);
          assert.ok(Math.abs(photo.x - (-.16 + aperture.cx * .0132)) < .005);
          assert.ok(Math.abs(photo.y - (-.16 + aperture.cy * .0132)) < .005);
        }
        const frameToggle = page.locator('[data-frame-toggle="' + key + '"]');
        await frameToggle.uncheck();
        assert.equal(await card.locator('.cosmetic-layers--avatar,.has-calibrated-portrait,.is-packaged').count(), 0);
        assert.equal(await page.locator('.moon-card .cosmetic-layers--avatar').count(), 6, 'Only this family loses its frame');
        await frameToggle.check();
        assert.equal(await card.locator('.has-calibrated-portrait').count(), 3);
        assert.equal(await portraits.evaluateAll(nodes => nodes.every(node => {
          const frame = node.querySelector('.cosmetic-layers--avatar').getBoundingClientRect();
          const sample = node.closest('figure');
          if (!sample) return true;
          const caption = sample.querySelector('figcaption').getBoundingClientRect();
          return frame.bottom <= caption.top + 1;
        })), true, 'Frame must not overlap its caption');
        assert.equal(await hero.locator('.hero-banner').evaluate(async image => { await image.decode(); return image.naturalWidth > 0; }), true);
        assert.equal(await hero.locator('img[src*="-sky-"]').count(), 0);
        for (const role of Object.keys(config.roles)) {
          const control = page.locator('[data-moon="' + key + '"][data-layer-toggle="' + role + '"]');
          const layers = hero.locator('[data-preview-role="' + role + '"]');
          assert.ok(await layers.count() > 0, family.label + ': missing ' + role);
          await control.uncheck();
          assert.equal(await layers.evaluateAll(images => images.every(image => getComputedStyle(image).visibility === 'hidden')), true);
          assert.equal(await page.locator('.moon-hero img[style*="visibility: hidden"]').count(), await layers.count(), 'toggle must affect only its family/asset');
          await control.check();
        }
      }
      await page.locator('#toggle-wind').click();
      assert.equal(await page.locator('#toggle-wind').getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('.moon-hero .cosmetic-layer').evaluateAll(images => images.every(image => getComputedStyle(image).animationPlayState === 'paused')), true);
      await page.locator('#toggle-wind').click();
      const movingHero = page.locator('[data-moon-hero="vermelha"]');
      await movingHero.evaluate(hero => hero.scrollIntoView({ behavior: 'instant', block: 'center' }));
      await page.waitForFunction(() => document.querySelector('[data-moon-hero="vermelha"] .cosmetic-layers').classList.contains('is-visible'));
      const cloud = movingHero.locator('[data-preview-role="clouds"]').first();
      const before = await cloud.evaluate(image => getComputedStyle(image).transform);
      await page.waitForTimeout(250);
      assert.notEqual(await cloud.evaluate(image => getComputedStyle(image).transform), before, 'wind must move after resume');
      await page.locator('#local-banner').setInputFiles(path.join(root, 'home/static/brand/human.webp'));
      assert.equal(await page.locator('.moon-hero>.hero-banner').evaluateAll(images => images.every(image => image.src.startsWith('blob:'))), true);
      await page.locator('#banner-reset').click();
      assert.equal(await page.locator('.moon-hero>.hero-banner').evaluateAll(images => images.every(image => image.src.endsWith('/brand/world.webp'))), true);
      await page.locator('#local-banner').setInputFiles({ name: 'not-an-image.txt', mimeType: 'text/plain', buffer: Buffer.from('not an image') });
      assert.match(await page.locator('#preview-status').innerText(), /PNG, JPEG, WebP ou GIF/);
      await page.locator('#banner-reset').click();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
      const textClear = await page.locator('.hero-copy').evaluateAll(copies => copies.every(copy => {
        const box = copy.getBoundingClientRect();
        return [...copy.querySelectorAll('strong,small')].every(text => {
          const rect = text.getBoundingClientRect();
          return rect.left >= box.left && rect.right <= box.right + 1 && rect.bottom <= box.bottom + 1;
        });
      }));
      assert.equal(textClear, true);
      await page.evaluate(() => { document.activeElement?.blur(); document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo({ top: 0, behavior: 'instant' }); });
      await page.screenshot({ path: path.join(output, 'three-moons-' + width + '.png'), fullPage: true });
      await page.locator('#original-comparisons summary').click();
      const original = page.locator('.original-red');
      assert.equal(await original.evaluate(async image => { await image.decode(); return image.naturalWidth > 0; }), true);
      assert.match(await page.locator('.arcane').evaluate(hero => getComputedStyle(hero).backgroundImage), /arcane-banner\.svg/);
      assert.deepEqual(errors, []);
      assert.deepEqual(network, [], 'local banner may not upload or make remote requests');
      await page.close();
      console.log(width + 'px: three overlay packages, 18 transparent assets, six split-foreground controls, all toggles, wind, local banner and comparisons OK.');
    }
    console.log('Screenshots: ' + output);
  } finally { await browser.close(); }
}

async function main() {
    if (process.argv.includes('--schema-test')) { testFrameSchema(); return; }
    const snapshot = buildSnapshot();
    const frames = buildFrames();
    const source = sourceFor(snapshot, frames);
    if (process.argv.includes('--server-test')) { testServerFrames(frames); return; }
    if (process.argv.includes('--check') || process.argv.includes('--browser-test')) {
      assert.equal(fs.readFileSync(snapshotPath, 'utf8'), source, 'Snapshot is stale; run build-moon-preview.cjs');
      console.log('Three-theme snapshot matches the real manifests.');
    } else if (!process.argv.includes('--test')) {
      fs.writeFileSync(snapshotPath, source);
      console.log('Generated BonfireMoonPreviews: ' + Object.keys(snapshot).join(', '));
    }
    if (process.argv.includes('--test')) { testValidation(snapshot); testFrameSchema(); testServerFrames(frames); }
    if (process.argv.includes('--browser-test')) await browserTest(snapshot);
}
if (require.main === module) {
  main().catch(error => {
    console.error('Moon preview not ready: ' + error.message);
    process.exitCode = 1;
  });
}
module.exports = { buildSnapshot, buildFrames, sourceFor, readConfig, validateManifest, validateFrame, testFrameSchema };
