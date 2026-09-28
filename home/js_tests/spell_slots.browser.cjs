/* Chromium com o cartão real da ficha e respostas controladas.
 * BONFIRE_PLAYWRIGHT_MODULE=C:/.../playwright-core node --test home/js_tests/spell_slots.browser.cjs
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/home/pages/ficha_detail.html'), 'utf8');
const spellSlots = fs.readFileSync(path.join(root, 'static/js/spell_slots.js'), 'utf8');
const httpClient = fs.readFileSync(path.join(root, 'static/js/http.js'), 'utf8');
const fichaCss = fs.readFileSync(path.join(root, 'static/css/pages/ficha.css'), 'utf8');
const tailwind = fs.readFileSync(path.join(root, 'static/vendor/tailwind/tailwind-3.4.17-typography.js'));

assert.match(template, /data-slot-version="\{\{ s\.version \}\}"/);
assert.match(template, /name="operation_id"/);
assert.match(template, /name="expected_version"/);
assert.match(template, /\{% if partial_spell_slots %\}[\s\S]*spell_slots\.js[\s\S]*\{% endif %\}/);

function cardHtml(slot) {
  let card = template.match(/<article class="spell-slot-card[\s\S]*?<\/article>/)[0];
  card = card
    .replace('{% if s.total == 0 %}is-zero{% endif %}', slot.total === 0 ? 'is-zero' : '')
    .replace(/\{% csrf_token %\}/g, '')
    .replace(/\{% url 'personagem_usar_slot_magia' p\.id_personagem %\}/g, '/usar-slot/')
    .replace(/\{% url 'ficha_detail' p\.id_personagem %\}/g, '/ficha/7/')
    .replace(/\{% if s\.atual == 0 %\}disabled\{% endif %\}/g, slot.atual === 0 ? 'disabled' : '')
    .replace(/\{% if s\.atual == s\.total %\}disabled\{% endif %\}/g, slot.atual === slot.total ? 'disabled' : '')
    .replace(/\{% if pode_editar and s\.total > 0 %\}|\{% endif %\}/g, '')
    .replace(/\{\{ s\.nivel \}\}/g, String(slot.nivel))
    .replace(/\{\{ s\.version \}\}/g, slot.version)
    .replace(/\{\{ s\.total \}\}/g, String(slot.total))
    .replace(/\{\{ s\.atual \}\}/g, String(slot.atual))
    .replace(/\{%[\s\S]*?%\}/g, '');
  assert.equal(card.includes('{%'), false, 'cartão renderizado sem tags Django');
  return card;
}

function formFields(body) {
  const fields = {};
  const matcher = /name="([^"]+)"\r?\n\r?\n([^\r\n]*)/g;
  let match;
  while ((match = matcher.exec(body || ''))) fields[match[1]] = match[2];
  return fields;
}

async function harness(t, slot = { nivel: 2, atual: 2, total: 3, version: 'v1' }) {
  const requests = [];
  const pendingResponses = [];
  let wake;
  const server = http.createServer((req, res) => {
    if (req.url === '/usar-slot/?pending=1') {
      pendingResponses.push(res);
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.write('{"ok":');
      return;
    }
    const assets = {
      '/spell_slots.js': ['text/javascript; charset=utf-8', spellSlots],
      '/http.js': ['text/javascript; charset=utf-8', httpClient],
      '/ficha.css': ['text/css; charset=utf-8', fichaCss],
      '/tailwind.js': ['text/javascript; charset=utf-8', tailwind],
    };
    if (assets[req.url]) {
      res.setHeader('Content-Type', assets[req.url][0]);
      return res.end(assets[req.url][1]);
    }
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    return res.end(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><link rel="stylesheet" href="/ficha.css"><script src="/tailwind.js"></script><script src="/http.js" defer></script><script src="/spell_slots.js" defer></script></head><body><nav class="ficha-tabs"><button class="ficha-tab is-active" data-tab="magias" aria-selected="true">Magias</button></nav><main><div style="height:1200px"></div><div class="ficha-tabpanel is-active" data-tabpanel="magias">${cardHtml(slot)}</div><div style="height:900px"></div></main></body></html>`);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 900, height: 600 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/usar-slot/', async route => {
    const request = route.request();
    if (request.url().includes('pending=1')) return route.continue();
    const entry = { route, input: formFields(request.postData()) };
    requests.push(entry);
    if (wake) { wake(); wake = null; }
  });
  t.after(async () => {
    await browser.close();
    pendingResponses.forEach(response => { if (!response.writableEnded) response.end(); });
    await new Promise(resolve => server.close(resolve));
    assert.deepEqual(errors, [], 'sem erros JavaScript no navegador');
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/ficha/7/?aba=magias`, { waitUntil: 'load' });
  return {
    page,
    async next(index) {
      if (!requests[index]) await new Promise(resolve => { wake = resolve; });
      return requests[index];
    },
    reply(entry, body, status = 200) {
      return entry.route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    },
    requests,
  };
}

function response(operationId, slot, version, ok = true, message = 'Slot atualizado.') {
  return { ok, operation_id: operationId, version, slot, message, replayed: false };
}

test('consome e devolve slots confirmados pelo servidor', async t => {
  const h = await harness(t);
  await h.page.locator('[data-slot-action="gastar"]').click();
  const spend = await h.next(0);
  assert.deepEqual({ nivel: spend.input.nivel, acao: spend.input.acao, expected_version: spend.input.expected_version }, { nivel: '2', acao: 'gastar', expected_version: 'v1' });
  assert.match(spend.input.operation_id, /^[0-9a-f-]{36}$/i);
  await h.reply(spend, response(spend.input.operation_id, { nivel: 2, atual: 1, total: 3 }, 'v2'));
  await h.page.getByText('1', { exact: true }).waitFor();
  assert.equal(await h.page.evaluate(() => document.activeElement.matches('[data-slot-action="gastar"]')), true,
    'êxito normal restaura o foco sem trocar de aba');
  await h.page.locator('[data-slot-action="desfazer"]').click();
  const restore = await h.next(1);
  assert.equal(restore.input.acao, 'desfazer');
  assert.equal(restore.input.expected_version, 'v2');
  await h.reply(restore, response(restore.input.operation_id, { nivel: 2, atual: 2, total: 3 }, 'v3'));
  assert.equal(await h.page.locator('[data-slot-atual]').innerText(), '2');
  assert.equal(await h.page.locator('[data-spell-slot-card]').getAttribute('data-slot-version'), 'v3');
});

test('duplo clique envia um único POST enquanto o cartão está bloqueado', async t => {
  const h = await harness(t);
  await h.page.locator('[data-slot-action="gastar"]').dblclick();
  const entry = await h.next(0);
  await new Promise(resolve => setTimeout(resolve, 80));
  assert.equal(h.requests.length, 1);
  assert.equal(await h.page.locator('[data-spell-slot-card]').getAttribute('aria-busy'), 'true');
  await h.reply(entry, response(entry.input.operation_id, { nivel: 2, atual: 1, total: 3 }, 'v2'));
});

test('conflito reconcilia o snapshot e não repete o POST', async t => {
  const h = await harness(t);
  await h.page.locator('[data-slot-action="gastar"]').click();
  const entry = await h.next(0);
  await h.reply(entry, response(entry.input.operation_id, { nivel: 2, atual: 0, total: 3 }, 'v9', false, 'Alterado em outra sessão.'), 409);
  await h.page.getByText('Alterado em outra sessão.', { exact: true }).waitFor();
  assert.equal(await h.page.locator('[data-slot-atual]').innerText(), '0');
  assert.equal(await h.page.locator('[data-slot-action="gastar"]').isDisabled(), true);
  assert.equal(h.requests.length, 1);
});

test('modo parcial desativado recarrega a ficha sem repetir o POST', async t => {
  const h = await harness(t);
  await h.page.locator('[data-slot-action="gastar"]').click();
  const entry = await h.next(0);
  const navigation = h.page.waitForEvent('framenavigated');
  await h.reply(entry, { ok: false, code: 'disabled', message: 'Atualize a página para usar o formulário.' }, 503);
  await navigation;
  assert.equal(h.requests.length, 1);
});

test('falha de rede permite repetir a mesma operação e impede o outro botão', async t => {
  const h = await harness(t);
  await h.page.locator('[data-slot-action="gastar"]').click();
  const first = await h.next(0);
  await first.route.abort('failed');
  await h.page.getByText(/Resultado não confirmado/).waitFor();
  assert.equal(await h.page.locator('[data-slot-action="desfazer"]').isDisabled(), true);
  await h.page.locator('[data-slot-action="gastar"]').click();
  const retry = await h.next(1);
  assert.equal(retry.input.operation_id, first.input.operation_id);
  assert.equal(retry.input.acao, first.input.acao);
  await h.reply(retry, response(retry.input.operation_id, { nivel: 2, atual: 1, total: 3 }, 'v2'));
});

test('timeout mantém a operação para uma repetição explícita', async t => {
  const h = await harness(t);
  await h.page.evaluate(() => {
    const original = window.BonfireHttp.postFormJson;
    window.BonfireHttp.postFormJson = (url, data) => original(url, data, { timeoutMs: 20 });
  });
  await h.page.locator('[data-slot-action="gastar"]').click();
  const first = await h.next(0);
  await h.page.getByText(/Resultado não confirmado/).waitFor();
  await h.page.locator('[data-slot-action="gastar"]').click();
  const retry = await h.next(1);
  assert.equal(retry.input.operation_id, first.input.operation_id);
  await h.reply(retry, response(retry.input.operation_id, { nivel: 2, atual: 1, total: 3 }, 'v2'));
});

test('corpo JSON pendente após os cabeçalhos também expira e preserva a operação', async t => {
  const h = await harness(t);
  await h.page.evaluate(() => {
    const original = window.BonfireHttp.postFormJson;
    let calls = 0;
    window.BonfireHttp.postFormJson = (url, data) => {
      calls += 1;
      return original(calls === 1 ? `${url}?pending=1` : url, data, { timeoutMs: 40 });
    };
  });
  await h.page.locator('[data-slot-action="gastar"]').click();
  await h.page.getByText(/Resultado não confirmado/).waitFor();
  const operationId = await h.page.locator('[data-slot-action="gastar"]').evaluate(button => button.form.querySelector('[name="operation_id"]').value);
  assert.match(operationId, /^[0-9a-f-]{36}$/i);
  await h.page.locator('[data-slot-action="gastar"]').click();
  const retry = await h.next(0);
  assert.equal(retry.input.operation_id, operationId);
  await h.reply(retry, response(retry.input.operation_id, { nivel: 2, atual: 1, total: 3 }, 'v2'));
});

test('no limite conserva aba e rolagem e move foco ao cartão sem rolar', async t => {
  const h = await harness(t, { nivel: 2, atual: 1, total: 3, version: 'v1' });
  await h.page.evaluate(() => {
    window.scrollTo(0, 700);
    document.querySelector('[data-slot-action="gastar"]').focus({ preventScroll: true });
    document.querySelector('[data-spell-slot-form]').requestSubmit(document.querySelector('[data-slot-action="gastar"]'));
  });
  const entry = await h.next(0);
  const scrollBefore = await h.page.evaluate(() => window.scrollY);
  await h.reply(entry, response(entry.input.operation_id, { nivel: 2, atual: 0, total: 3 }, 'v2'));
  await h.page.getByText('0', { exact: true }).waitFor();
  assert.equal(await h.page.evaluate(() => document.activeElement.matches('[data-spell-slot-card]')), true);
  assert.equal(await h.page.evaluate(() => document.querySelector('[data-tab="magias"]').getAttribute('aria-selected')), 'true');
  assert.equal(await h.page.evaluate(() => window.scrollY), scrollBefore);
});

test('HTML ou conteúdo inesperado preserva operação para reconciliação manual', async t => {
  const h = await harness(t);
  await h.page.locator('[data-slot-action="gastar"]').click();
  const entry = await h.next(0);
  await entry.route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: '<html>login</html>' });
  await h.page.getByText(/Resultado não confirmado/).waitFor();
  assert.equal(await h.page.locator('[data-slot-atual]').innerText(), '2');
  await h.page.locator('[data-slot-action="gastar"]').click();
  const retry = await h.next(1);
  assert.equal(retry.input.operation_id, entry.input.operation_id);
  await h.reply(retry, response(retry.input.operation_id, { nivel: 2, atual: 1, total: 3 }, 'v2'));
});
