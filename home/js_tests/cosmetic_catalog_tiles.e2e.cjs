/* Isolated Django component and real local media; no environment files or DB. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require(process.env.BONFIRE_PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const root = path.resolve(__dirname, '../..');
  const python = process.env.BONFIRE_PYTHON || path.resolve(root, '../BonfireSite-main/.venv/Scripts/python.exe');
  const code = "from django.conf import settings; settings.configure(SECRET_KEY='isolated-catalog',STATIC_URL='/static/',SITE_POSTGRES_TABLES={},INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','home'],DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}},TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','APP_DIRS':True}]); import django; django.setup(); import json; from home.test_cosmetic_catalog_tiles import browser_fixture; print(json.dumps(browser_fixture()))";
  const render = spawnSync(python, ['-B', '-c', code], {cwd: root, encoding: 'utf8', env: {...process.env, PYTHONIOENCODING:'utf-8'}});
  assert.equal(render.status, 0, render.stderr);
  const fixture = JSON.parse(render.stdout);
  const artifacts = process.env.BONFIRE_ARTIFACT_DIR || fs.mkdtempSync(path.join(os.tmpdir(), 'bonfire-catalog-dialog-'));
  fs.mkdirSync(artifacts, {recursive:true});
  const browser = await chromium.launch({headless:true, channel:process.env.BONFIRE_BROWSER_CHANNEL || 'msedge'});
  const errors = [], missing = new Set();
  async function routes(page, requests) {
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      assert.equal(url.origin, 'https://catalog.invalid', 'no arbitrary remote URLs');
      assert.equal(route.request().method(), 'GET', 'no profile writes');
      if (url.pathname === '/') return route.fulfill({body:fixture.html, contentType:'text/html; charset=utf-8'});
      if (url.pathname === '/catalog-preview/') {
        assert.equal(url.searchParams.has('slug'), false);
        assert.ok(['perfil','ficha'].includes(url.searchParams.get('escopo')));
        requests.push(url.href);
        const payload = fixture.previews[url.searchParams.get('tipo') + ':' + url.searchParams.get('key')];
        if (!payload) return route.fulfill({status:404, json:{error:'unknown'}});
        if (payload.key === 'gold-trim') await new Promise(resolve => setTimeout(resolve, 350));
        return route.fulfill({json:payload}).catch(() => {});
      }
      if (!url.pathname.startsWith('/static/')) return route.fulfill({status:404,body:''});
      const staticRoot = path.join(root, 'home/static');
      const asset = path.resolve(staticRoot, decodeURIComponent(url.pathname.slice('/static/'.length)));
      assert.ok(asset.startsWith(staticRoot + path.sep));
      if (!fs.existsSync(asset)) { missing.add(url.pathname); return route.fulfill({status:404,body:''}); }
      return route.fulfill({path:asset});
    });
  }
  try {
    for (const width of [390,1280]) {
      const page = await browser.newPage({viewport:{width,height:844}});
      const requests = []; await routes(page, requests);
      await page.goto('https://catalog.invalid/', {waitUntil:'networkidle'});
      assert.equal(requests.length, 0, 'no eager candidate requests');
      assert.equal(await page.locator('[data-cosmetic-layers]').count(), 0);
      assert.equal(await page.locator('#perfil-form [data-catalog-open]').count(), 3);
      const initialFrames = page.locator('[data-cosmetic-catalog]').filter({has:page.locator('#id_avatar_frame')});
      await initialFrames.locator('[data-catalog-open]').click();
      await initialFrames.locator('.public-profile-page').waitFor();
      assert.equal(await initialFrames.locator('.public-profile-page').getAttribute('data-theme-category'), 'especial');
      assert.equal(await initialFrames.locator('.public-profile-page').evaluate(node => node.classList.contains('skin-current-fixture')), true, 'frame preview preserves current skin');
      await page.keyboard.press('Escape');
      for (const [id, key, lockedKey] of [
        ['id_profile_theme','custom','exclusive'], ['id_avatar_frame','ember-ring','elo-diamante-fechada'],
        ['id_profile_effect','glass','starfall'], ['ficha-frame-select','ember-ring','elo-diamante-fechada'],
        ['ficha-effect-select','glass','starfall']]) {
        const select = page.locator('#' + id);
        const catalog = page.locator('[data-cosmetic-catalog]').filter({has:select});
        const launcher = catalog.locator('[data-catalog-open]');
        const dialog = catalog.locator('dialog');
        const apply = catalog.locator('[data-catalog-apply]');
        const initial = await select.inputValue();
        await select.evaluate(node => { node.dataset.changes='0'; node.addEventListener('change', () => node.dataset.changes++); });
        await launcher.click();
        await apply.waitFor({state:'visible'});
        await page.waitForFunction(el => !el.disabled, await apply.elementHandle());
        const tile = catalog.locator(`[data-catalog-key="${key}"]`);
        await tile.click();
        await page.waitForFunction(el => !el.disabled, await apply.elementHandle());
        assert.equal(await select.inputValue(), initial, 'candidate is not committed');
        await page.keyboard.press('Escape');
        await dialog.waitFor({state:'hidden'});
        assert.equal(await launcher.evaluate(el => el === document.activeElement), true);
        assert.equal(await select.inputValue(), initial);
        assert.equal(await catalog.locator('[data-cosmetic-layers]').count(), 0, 'close disposes layers');
        const count = requests.length;
        await launcher.click(); await tile.click();
        await page.waitForFunction(el => !el.disabled, await apply.elementHandle());
        assert.equal(requests.length, count, 'in-memory candidate cache');
        await apply.click();
        assert.equal(await select.inputValue(), key);
        assert.equal(await select.getAttribute('data-changes'), '1');
        if (id === 'id_profile_theme') {
          assert.equal(await page.locator('#profile-root').getAttribute('data-theme-category'), 'classico');
          assert.equal(await page.locator('#profile-root').evaluate(node => node.classList.contains('skin-current-fixture')), false, 'classic apply clears previous special skin');
        }
        assert.equal(await select.evaluate(el => new FormData(el.form).get(el.name)), key);
        await launcher.click();
        if (id === 'id_profile_theme') await catalog.locator('[data-catalog-category="especial"]').click();
        const locked = catalog.locator(`[data-catalog-key="${lockedKey}"]`);
        assert.equal(await locked.isEnabled(), true, 'locked tiles can preview');
        await locked.click();
        await page.waitForFunction(el => el.textContent === '', await catalog.locator('[data-catalog-status]').elementHandle());
        assert.equal(await apply.isDisabled(), true);
        assert.equal(await catalog.locator('[data-catalog-acquisition]').isVisible(), true);
        await apply.evaluate(button => { button.disabled=false; button.click(); });
        assert.equal(await select.inputValue(), key, 'spoofed locked apply rejected');
        await page.keyboard.press('Escape');
        assert.equal(await select.inputValue(), key);
        await launcher.click();
        if (id === 'id_profile_theme') await catalog.locator('[data-catalog-category="classico"]').click();
        const search = catalog.locator('[data-catalog-filter]');
        await search.fill('sem-resultados-aqui');
        assert.equal(await catalog.locator('[data-catalog-empty]').isVisible(), true);
        await search.fill('');
        await search.press('Enter');
        assert.equal(await dialog.isVisible(), true, 'search Enter never submits the profile');
        await tile.focus(); await page.keyboard.press('Home');
        assert.equal(await catalog.locator('[data-catalog-tile]:focus').count(), 1);
        await page.waitForFunction(el => !el.disabled, await apply.elementHandle());
        await apply.focus(); await page.keyboard.press('Tab');
        assert.equal(await catalog.locator('[data-catalog-close]').first().evaluate(el => el === document.activeElement), true, 'focus wraps');
        await page.keyboard.press('Shift+Tab');
        assert.equal(await apply.evaluate(el => el === document.activeElement), true);
        await catalog.locator('[data-catalog-close]').first().click();
        assert.equal(await select.inputValue(), key);
      }
      const frames = page.locator('[data-cosmetic-catalog]').filter({has:page.locator('#id_avatar_frame')});
      const themes = page.locator('[data-cosmetic-catalog]').filter({has:page.locator('#id_profile_theme')});
      await themes.locator('[data-catalog-open]').click();
      await themes.locator('[data-catalog-category="especial"]').click();
      await themes.locator('[data-catalog-key="owned-special"]').click();
      await page.waitForFunction(el => !el.disabled, await themes.locator('[data-catalog-apply]').elementHandle());
      assert.equal(await themes.locator('.public-profile-page').getAttribute('data-theme-category'), 'especial');
      assert.equal(await page.locator('#profile-root').getAttribute('data-theme-category'), 'classico', 'candidate does not change current category');
      await themes.locator('[data-catalog-apply]').click();
      assert.equal(await page.locator('#profile-root').getAttribute('data-theme-category'), 'especial');
      assert.equal(await page.locator('#profile-root').evaluate(node => node.classList.contains('skin-owned-fixture')), true);
      await frames.locator('[data-catalog-open]').click();
      await frames.locator('[data-catalog-key="gold-trim"]').click();
      await frames.locator('[data-catalog-key="elo-diamante-fechada"]').click();
      await page.waitForFunction(el => el.textContent === '', await frames.locator('[data-catalog-status]').elementHandle());
      await page.waitForTimeout(450);
      assert.equal(await frames.locator('[data-catalog-name]').textContent(), 'Elmo de Diamante', 'stale response cannot replace focused candidate');
      assert.equal(await frames.locator('.public-profile-page').evaluate(node => node.classList.contains('skin-owned-fixture')), true);
      for (const image of await frames.locator('dialog img').all()) { await image.scrollIntoViewIfNeeded(); await image.evaluate(img => img.decode()); }
      const fit = await frames.locator('dialog').evaluate(dialog => ({fits:dialog.getBoundingClientRect().left>=0 && dialog.getBoundingClientRect().right<=innerWidth, overflow:dialog.scrollWidth>dialog.clientWidth+1}));
      assert.deepEqual(fit, {fits:true,overflow:false});
      await frames.locator('dialog').evaluate(dialog => {dialog.scrollTop=0;});
      await page.screenshot({path:path.join(artifacts, `catalog-dialog-${width}.png`)});
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('[data-cosmetic-layers]').count(), 0);
      assert.equal(await page.locator('iframe').count(), 0);
      await page.close();
      console.log(`${width}px: lazy preview/cache, apply/cancel, locked spoof, keyboard/focus, ficha, cleanup, layout OK`);
    }
    const nojs = await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
    const fallback = await nojs.newPage(); const requests=[]; await routes(fallback, requests);
    await fallback.goto('https://catalog.invalid/');
    assert.equal(await fallback.locator('select:visible').count(), 5);
    assert.equal(await fallback.locator('[data-catalog-controls]:visible').count(), 0);
    assert.equal(await fallback.locator('#id_avatar_frame option:disabled').count(), 1);
    assert.equal(requests.length, 0);
    await nojs.close();
    assert.deepEqual(errors, []); assert.deepEqual([...missing], []);
    console.log(`No-JS fallback OK; screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode=1;});
