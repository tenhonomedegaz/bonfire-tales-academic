/* Real Django partial + local assets; no server, login, database or purchases. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE);

(async () => {
  const root = path.resolve(__dirname, '../..');
  const render = spawnSync(process.env.BONFIRE_PYTHON || 'python', ['-c',
    "import django; django.setup(); from home.test_cosmetic_catalog_tiles import browser_fixture; print(browser_fixture())"],
  { cwd: root, encoding: 'utf8', env: { ...process.env, DJANGO_DEBUG: '1',
    DB_ENGINE: 'postgresql', DJANGO_SETTINGS_MODULE: 'bonfire.settings', PYTHONIOENCODING: 'utf-8' } });
  assert.equal(render.status, 0, render.stderr);
  const artifacts = process.env.BONFIRE_ARTIFACT_DIR || fs.mkdtempSync(path.join(os.tmpdir(), 'bonfire-catalog-'));
  fs.mkdirSync(artifacts, { recursive: true });
  const fixture = path.join(artifacts, 'catalog.html');
  fs.writeFileSync(fixture, render.stdout);
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const missingAssets = new Set();
  async function localAssets(page) {
    await page.route('https://catalog.invalid/static/**', route => {
      const relative = decodeURIComponent(new URL(route.request().url()).pathname.slice('/static/'.length));
      const staticRoot = path.join(root, 'home/static');
      const asset = path.resolve(staticRoot, relative);
      assert.ok(asset.startsWith(staticRoot + path.sep));
      if (!fs.existsSync(asset)) {
        missingAssets.add(relative);
        return route.fulfill({ status: 404, body: '' });
      }
      return route.fulfill({ path: asset });
    });
  }
  const ids = ['id_avatar_frame', 'id_profile_effect', 'ficha-frame-select', 'ficha-effect-select'];
  try {
    for (const width of [360, 1280]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      await localAssets(page);
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(pathToFileURL(fixture).href);
      for (const id of ids) {
        const select = page.locator('#' + id);
        const catalog = page.locator('[data-cosmetic-catalog]').filter({ has: select });
        await catalog.waitFor({ state: 'visible' });
        assert.equal(await select.isVisible(), false);
        const frame = id.includes('frame');
        const next = frame ? 'ember-ring' : 'glass';
        await select.evaluate(element => {
          element.dataset.inputEvents = '0'; element.dataset.changeEvents = '0';
          element.addEventListener('input', () => element.dataset.inputEvents++);
          element.addEventListener('change', () => element.dataset.changeEvents++);
        });
        const radio = catalog.locator(`input[type="radio"][value="${next}"]`);
        await radio.check();
        assert.equal(await select.inputValue(), next);
        assert.equal(await select.getAttribute('data-input-events'), '1');
        assert.equal(await select.getAttribute('data-change-events'), '1');
        assert.equal(await radio.isChecked(), true);
        const formValues = await select.evaluate(element => Object.fromEntries(new FormData(element.form)));
        assert.equal(formValues[await select.getAttribute('name')], next);
        const locked = catalog.locator('input[type="radio"]:disabled');
        assert.ok(await locked.count() > 0);
        await locked.first().evaluate(element => {
          element.checked = true;
          element.dispatchEvent(new Event('change', { bubbles: true }));
        });
        assert.equal(await select.inputValue(), next, 'locked UI must not change canonical select');
        assert.equal(await locked.first().isChecked(), false);
        await select.evaluate(element => {
          element.value = 'none'; element.dispatchEvent(new Event('change', { bubbles: true }));
        });
        assert.equal(await catalog.locator('input[value="none"]').isChecked(), true);
        const search = catalog.locator('[data-catalog-filter]');
        await search.fill(frame ? 'EXPLORACAO' : 'ESTRELAS');
        assert.equal(await catalog.locator('[data-catalog-tile]:visible').count(), 1);
        await search.fill('nenhuma-opcao-deste-nome');
        assert.equal(await catalog.locator('[data-catalog-empty]').isVisible(), true);
        await search.fill('');
        await radio.focus();
        await page.keyboard.press('Space');
        assert.equal(await select.inputValue(), next, 'keyboard selection');
        await select.evaluate(element => element.form.reset());
        await page.waitForFunction(id => document.querySelector(`#${id}`).value === 'none' &&
          document.querySelector(`input[name="catalog_${id}"][value="none"]`).checked, id);
      }
      await page.locator('main').scrollIntoViewIfNeeded();
      // Load lazy public art across both catalogs, including locked helmets.
      for (const image of await page.locator('.cosmetic-catalog img').all()) {
        await image.scrollIntoViewIfNeeded();
        await image.evaluate(image => image.decode());
      }
      await page.waitForFunction(() => document.querySelectorAll('.cosmetic-effect-sample[data-profile-effect="starfall"] > .profile-effect-layer').length === 2);
      const calibration = await page.locator('[data-catalog-tile] [data-aperture-x]').evaluateAll(layers =>
        layers.map(layer => {
          const owner = layer.parentElement;
          const expectedSize = Number(layer.dataset.apertureSize) * 1.32;
          return owner.classList.contains('has-calibrated-portrait') &&
            Math.abs(parseFloat(owner.style.getPropertyValue('--portrait-size')) - expectedSize) < .001;
        }));
      assert.ok(calibration.length > 0, 'calibrated packages must be present');
      assert.ok(calibration.every(Boolean), 'aperture attributes must reach the renderer');
      assert.equal(await page.locator('.cosmetic-effect-sample[data-profile-effect="none"] > .profile-effect-layer').count(), 0);
      const layout = await page.evaluate(() => {
        const overlaps = [...document.querySelectorAll('.cosmetic-catalog-tile')].filter(tile => {
          const preview = tile.querySelector('.cosmetic-catalog-preview').getBoundingClientRect();
          const name = tile.querySelector('.cosmetic-catalog-name').getBoundingClientRect();
          return preview.bottom > name.top + 1;
        }).length;
        const samples = [...document.querySelectorAll('.cosmetic-catalog-preview')].map(node => node.getBoundingClientRect().height);
        return { fits: document.documentElement.scrollWidth <= innerWidth + 1, overlaps,
          sizes: samples.every(height => height >= 50 && height <= 90),
          loaded: [...document.querySelectorAll('.cosmetic-catalog img')].every(image => image.naturalWidth > 0) };
      });
      assert.deepEqual(layout, { fits: true, overlaps: 0, sizes: true, loaded: true });
      await page.screenshot({ path: path.join(artifacts, `catalog-${width}.png`), fullPage: true });
      assert.deepEqual(errors, []);
      await page.close();
      console.log(`${width}px: sync, locks, filter, keyboard, reset, media and layout OK`);
    }
    const nojs = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 360, height: 800 } });
    const fallback = await nojs.newPage();
    await localAssets(fallback);
    await fallback.goto(pathToFileURL(fixture).href);
    for (const id of ids) assert.equal(await fallback.locator('#' + id).isVisible(), true);
    assert.equal(await fallback.locator('[data-catalog-controls]:visible').count(), 0);
    await fallback.locator('#id_avatar_frame').selectOption('ember-ring');
    assert.equal(await fallback.locator('#id_avatar_frame').inputValue(), 'ember-ring');
    await nojs.close();
    assert.deepEqual([...missingAssets], [], 'all integrated assets must be present');
    console.log(`No-JS fallback OK; screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
