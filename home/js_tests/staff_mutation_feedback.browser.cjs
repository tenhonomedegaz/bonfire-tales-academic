const assert = require('node:assert/strict');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE);

(async () => {
  const browser = await chromium.launch({headless: true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? {executablePath: process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH}
      : {channel: 'msedge'})});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent(`
      <div data-carteira-display>10 PO</div>
      <span data-ficha-aventuras>1</span><span data-ficha-teto>nível 1</span>
      <span data-ficha-braseiros>0</span><span data-ficha-ca>12</span><span data-ficha-pv>10</span>
      <details data-missao-details="7" open><summary>Missão</summary>
        <div id="lvl-aventuras-staffbox"><form action="https://test.local/mission" data-aventura-form>
          <input name="csrfmiddlewaretoken" value="token"><input name="nome_aventura" value="Mesa guardada">
          <button type="submit">Registrar</button></form></div>
      </details>
      <div id="ficha-concessoes-dinamico"><form action="https://test.local/grant" data-conceder-form>
        <input name="csrfmiddlewaretoken" value="token"><input name="origem_nota" value="Prêmio guardado">
        <button type="submit">Conceder</button></form></div>`);
    await page.evaluate(() => {
      window.__responses = [];
      window.fetch = () => {
        const response = window.__responses.shift();
        return response === 'offline' ? Promise.reject(Error('offline')) :
          Promise.resolve({ok: response.ok, json: () => Promise.resolve(response.body)});
      };
    });
    await page.addScriptTag({path: 'home/static/js/editar_ficha.js'});
    async function enqueue(response) { await page.evaluate(value => window.__responses.push(value), response); }
    async function submit(selector) { await page.locator(selector).evaluate(form => form.requestSubmit()); }

    await enqueue('offline');
    await submit('[data-aventura-form]');
    await page.locator('[data-aventura-form] + [data-action-feedback]').waitFor();
    assert.match(await page.locator('[data-aventura-form] + [data-action-feedback]').innerText(), /conexão falhou/);
    assert.equal(await page.locator('[name=nome_aventura]').inputValue(), 'Mesa guardada');
    assert.equal(await page.locator('[data-aventura-form] button').isEnabled(), true);
    assert.equal(await page.locator('[data-ficha-aventuras]').innerText(), '1');
    await enqueue({ok: true, body: {staffbox_html: '<div id="lvl-aventuras-staffbox">Mesa registrada</div>',
      progressao: {aventuras: 2, nivel_label: 'nível 2', braseiros: 1}, carteira_display: '20 PO'}});
    await submit('[data-aventura-form]');
    await page.getByText('Mesa registrada').waitFor();
    assert.equal(await page.locator('[data-missao-details="7"]').evaluate(el => el.open), true);
    assert.equal(await page.locator('[data-ficha-aventuras]').innerText(), '2');
    assert.equal(await page.locator('[data-carteira-display]').innerText(), '20 PO');

    await enqueue('offline');
    await submit('[data-conceder-form]');
    await page.locator('[data-conceder-form] + [data-action-feedback]').waitFor();
    assert.match(await page.locator('[data-conceder-form] + [data-action-feedback]').innerText(), /conexão falhou/);
    assert.equal(await page.locator('[name=origem_nota]').inputValue(), 'Prêmio guardado');
    assert.equal(await page.locator('[data-conceder-form] button').isEnabled(), true);
    await enqueue({ok: false, body: {concessoes_html: `<div id="ficha-concessoes-dinamico">Item inválido
      <form action="https://test.local/grant" data-conceder-form>
        <input name="csrfmiddlewaretoken" value="token"><button type="submit">Conceder</button>
      </form></div>`,
      inventario_html: 'inventário de erro', carteira_display: '999 PO', ficha: {ca: 99, pv_maximo: 99}}});
    await submit('[data-conceder-form]');
    await page.getByText('Item inválido').waitFor();
    assert.equal(await page.locator('[data-carteira-display]').innerText(), '20 PO');
    assert.equal(await page.locator('[data-ficha-ca]').innerText(), '12');
    await enqueue({ok: true, body: {
      concessoes_html: '<div id="ficha-concessoes-dinamico">Item concedido</div>',
      inventario_html: 'inventário válido', carteira_display: '21 PO', ficha: {ca: 13, pv_maximo: 11}}});
    await submit('[data-conceder-form]');
    await page.getByText('Item concedido').waitFor();
    assert.equal(await page.locator('[data-carteira-display]').innerText(), '21 PO');
    assert.equal(await page.locator('[data-ficha-ca]').innerText(), '13');
    assert.equal(await page.locator('[data-ficha-pv]').innerText(), '11');
    assert.deepEqual(errors, []);
    console.log('staff: falhas exibem aviso e preservam formulário; sucesso atualiza missão e concessão; erro HTTP conserva estado');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
