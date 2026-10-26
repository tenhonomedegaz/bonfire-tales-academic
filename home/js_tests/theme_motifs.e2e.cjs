const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE);

(async () => {
  const root = path.resolve(__dirname, '../..');
  const render = spawnSync('py', ['-3.14', '-c',
    'import django; django.setup(); from home.test_theme_motifs import browser_fixture; print(browser_fixture())'],
  { cwd: root, encoding: 'utf8', env: { ...process.env, DJANGO_SETTINGS_MODULE: 'bonfire.settings',
    DJANGO_DEBUG: '1', DB_ENGINE: 'postgresql', POSTGRES_URL: '', PYTHONIOENCODING: 'utf-8' } });
  assert.equal(render.status, 0, render.stderr);
  const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'bonfire-motif-qa-'));
  const html = path.join(artifacts, 'motifs.html');
  fs.writeFileSync(html, render.stdout);
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  try {
    for (const width of [1280, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(pathToFileURL(html).href);
      await page.locator('img').evaluate(image => image.decode());
      const backgrounds = new Set();
      const pictures = new Set();
      const navColors = new Set();
      for (const motif of ['none', 'facets', 'runes', 'sun', 'leaves', 'flames', 'thorns', 'crystal', 'moon', 'eclipse', 'bats']) {
        await page.locator(`#motif-${motif}`).check({ force: true });
        const result = await page.evaluate(() => ({
          motifs: [...document.querySelectorAll('[data-theme-motif]')].map(node => node.dataset.themeMotif),
          image: getComputedStyle(document.querySelector('.profile-header')).backgroundImage,
          fits: document.documentElement.scrollWidth <= innerWidth + 1,
          header: getComputedStyle(document.querySelector('.profile-header')).borderTopColor,
          save: getComputedStyle(document.querySelector('.profile-btn')).backgroundColor,
          nav: getComputedStyle(document.querySelector('.profile-nav')).backgroundColor,
        }));
        assert.ok(result.motifs.every(value => value === motif));
        assert.ok(result.fits, `overflow ${width}/${motif}`);
        backgrounds.add(result.image);
        assert.notEqual(result.save, 'rgb(165, 30, 40)', 'save must not retain fixed red');
        const shot = await page.locator('.profile-header').screenshot();
        pictures.add(crypto.createHash('sha256').update(shot).digest('hex'));
      }
      assert.equal(backgrounds.size, 11, 'each motif has its own CSS pattern');
      assert.equal(pictures.size, 11, 'patterns must produce distinct pixels');
      for (const accent of ['#34d399', '#a78bfa', '#7dd3fc']) {
        await page.evaluate(color => {
          const root = document.querySelector('#profile-root');
          root.style.setProperty('--profile-accent-solid', color);
          root.style.setProperty('--profile-surface', color);
        }, accent);
        navColors.add(await page.locator('.profile-nav').evaluate(node => getComputedStyle(node).backgroundColor));
      }
      assert.equal(navColors.size, 3, 'private navigation follows selected variables');
      const sync = await page.evaluate(() => {
        const target = document.querySelector('#profile-root');
        const source = document.querySelector('.public-profile-page');
        target.classList.add('effect-glass', 'layout-keep');
        const portrait = document.createElement('div');
        portrait.id = 'profile-avatar-main';
        portrait.className = 'profile-avatar-wrapper frame-old';
        const image = document.createElement('img');
        image.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg"/%3E';
        portrait.appendChild(image);
        target.appendChild(portrait);
        source.classList.add('effect-starfall');
        source.dataset.themeMotif = 'crystal';
        source.insertAdjacentHTML('beforeend', '<div class="public-profile-avatar frame-new is-packaged has-calibrated-portrait" style="--portrait-x:41%;--portrait-y:47%;--portrait-size:61%"><div data-cosmetic-layers class="cosmetic-layers cosmetic-layers--avatar"><span>authorized frame</span></div></div>');
        window.TemaSwatch.syncAuthorizedPreview(source, target);
        const first = target.classList.contains('effect-starfall') && !target.classList.contains('effect-glass') &&
          target.classList.contains('layout-keep') && portrait.classList.contains('frame-new') &&
          portrait.classList.contains('profile-avatar-wrapper') && portrait.firstElementChild === image &&
          portrait.querySelector('[data-cosmetic-layers]').textContent === 'authorized frame' &&
          portrait.style.getPropertyValue('--portrait-x') === '41%';
        source.querySelector('.public-profile-avatar').className = 'public-profile-avatar';
        source.querySelector('.public-profile-avatar').style.cssText = '';
        source.querySelector('.public-profile-avatar').innerHTML = '';
        window.TemaSwatch.syncAuthorizedPreview(source, target);
        const reset = !portrait.classList.contains('frame-new') && !portrait.classList.contains('has-calibrated-portrait') &&
          !portrait.querySelector('[data-cosmetic-layers]') && !portrait.style.getPropertyValue('--portrait-x') &&
          portrait.firstElementChild === image;
        portrait.remove();
        source.querySelector('.public-profile-avatar').remove();
        return first && reset;
      });
      assert.ok(sync, 'authorized effect/frame sync must preserve portrait/layout and reset stale layers');
      await page.evaluate(() => {
        const root = document.querySelector('#profile-root');
        root.style.setProperty('--profile-accent-solid', '#34d399');
        root.style.setProperty('--profile-surface', '#141418');
      });
      await page.screenshot({ path: path.join(artifacts, `motifs-${width}.png`), fullPage: true });
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log(JSON.stringify({ status: 'ok', viewports: [1280, 390], motifs: 11,
      checks: 'distinct pixels, all roots, variables, no overflow or page errors', artifacts }));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
