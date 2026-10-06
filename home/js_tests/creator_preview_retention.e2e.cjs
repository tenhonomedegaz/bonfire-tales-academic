const assert = require('node:assert/strict');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE);

(async () => {
  const browser = await chromium.launch({headless: true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? {executablePath: process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH}
      : {channel: 'msedge'})});
  try {
    const origin = process.env.PREVIEW_ORIGIN;
    const context = await browser.newContext();
    await context.addCookies([{name: process.env.PREVIEW_COOKIE_NAME,
      value: process.env.PREVIEW_COOKIE_VALUE, url: origin}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const response = await page.goto(origin + process.env.PREVIEW_PAGE);
    const form = page.locator('#criador-form');
    if (await form.count() !== 1) throw Error(`Criador: HTTP ${response.status()}, URL ${page.url()}, titulo ${await page.title()}`);
    const previewUrl = await form.getAttribute('data-preview-url');
    let mode = 'offline', pv = 17;
    await page.route(origin + previewUrl, route => {
      if (mode === 'offline') return route.abort('failed');
      if (mode === 'invalid') return route.fulfill({status: 400,
        contentType: 'application/json', body: JSON.stringify({ready: false, erros: ['Escolha inválida.']})});
      return route.fulfill({status: 200, contentType: 'application/json',
        body: JSON.stringify({ready: true, erros: [], pending_spell_choices: [],
          preview: {pv, ca: 14, pb: 2, nivel: 1, pv_completo: true, atributos: [
            {sig: 'FOR', valor: 15, mod: 2, save_prof: true}],
            pericias: [{nome: 'Atletismo'}]}})});
    });
    await page.evaluate(() => {
      for (const id of ['cf-raca', 'cf-classe', 'cf-antecedente']) {
        const select = document.getElementById(id);
        const first = [...select.options].find(option => option.value);
        if (!first) throw Error(`Sem opções em ${id}`);
        select.value = first.value;
        select.dispatchEvent(new Event('change', {bubbles: true}));
      }
      window.PointBuy.state = () => ({spent: 27, remaining: 0, complete: true});
      document.getElementById('criador-form').dispatchEvent(new Event('change', {bubbles: true}));
    });
    const status = page.locator('#cf-preview-status');
    const displayedPv = page.locator('#cf-preview [data-pv]');
    await status.getByText('prévia indisponível').waitFor();
    assert.equal(await displayedPv.innerText(), '—', 'sem cálculo anterior, falha não inventa valores');
    mode = 'valid';
    await form.evaluate(node => node.dispatchEvent(new Event('change', {bubbles: true})));
    await status.getByText('nível 1').waitFor();
    assert.equal(await displayedPv.innerText(), '17');
    const attrs = await page.locator('#cf-preview-attrs').innerHTML();
    const extra = await page.locator('#cf-preview-extra').innerHTML();
    async function refresh() {
      await form.evaluate(node => node.dispatchEvent(new Event('change', {bubbles: true})));
    }
    mode = 'offline';
    await refresh();
    await status.getByText(/prévia indisponível.*último cálculo válido/).waitFor();
    assert.equal(await displayedPv.innerText(), '17');
    assert.equal(await page.locator('#cf-preview-attrs').innerHTML(), attrs);
    assert.match(await page.locator('#cf-preview-extra').innerHTML(), /Atletismo/);
    mode = 'invalid';
    await refresh();
    await status.getByText(/prévia pendente.*último cálculo válido/).waitFor();
    assert.equal(await displayedPv.innerText(), '17');
    assert.match(await page.locator('#cf-preview-extra').innerText(), /Escolha inválida/);
    mode = 'valid'; pv = 20;
    await refresh();
    await page.waitForFunction(() => document.querySelector('#cf-preview [data-pv]').textContent === '20');
    assert.equal(await status.innerText(), 'nível 1');
    assert.notEqual(await page.locator('#cf-preview-extra').innerHTML(), '');
    assert.match(extra, /Atletismo/);
    await page.evaluate(() => {
      window.PointBuy.state = () => ({spent: 26, remaining: 1, complete: false});
      document.getElementById('criador-form').dispatchEvent(new Event('change', {bubbles: true}));
    });
    await status.getByText('atributos pendentes').waitFor();
    assert.equal(await displayedPv.innerText(), '—', 'point-buy incompleto invalida o cálculo');
    assert.deepEqual(errors, []);
    console.log(`${process.env.PREVIEW_PAGE}: falhas preservam último cálculo; recuperação atualiza; point-buy incompleto invalida`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
