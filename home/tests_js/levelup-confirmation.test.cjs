const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '..', 'static', 'js', 'subir_nivel.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
function response(status, body, redirected = false) {
  return { status, redirected, text: async () => body, json: async () => JSON.parse(body) };
}
function harness(replies) {
  function element() {
    return {
      dataset: {}, disabled: false, hidden: false, innerHTML: '', textContent: '', listeners: {},
      classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
      querySelector() { return null; }, querySelectorAll() { return []; },
      addEventListener(type, fn) { this.listeners[type] = fn; },
      removeAttribute() {}, scrollIntoView() {},
    };
  }
  const confirm = element(), previous = element(), feedback = element(), status = element();
  const main = element(), stepper = element(), review = element();
  review.dataset.step = 'revisar';
  const controls = { '[data-sn-confirm]': confirm, '[data-sn-prev]': previous };
  main.querySelector = key => controls[key] || null;
  main.querySelectorAll = key => key === '.cf-step[data-step]' ? [review] : [];
  const elements = { 'sn-main': main, 'sn-stepper': stepper, 'sn-feedback': feedback, 'sn-prev-status': status };
  const document = {
    getElementById: key => elements[key] || null,
    querySelector() { return null; }, addEventListener() {},
    createElement() {
      return { textContent: '', get innerHTML() {
        return String(this.textContent).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
      } };
    },
  };
  const calls = [];
  const window = {
    SN: { previewUrl: '/preview', aplicarUrl: '/apply', podeSubir: true, classeId: 1,
      csrf: 'test-csrf', fichaUrl: '/sheet', pageUrl: '/wizard' },
    crypto: { randomUUID: () => 'test-request-id' }, location: {},
  };
  vm.runInNewContext(source, {
    window, document, setTimeout, clearTimeout,
    fetch: async (url, options) => {
      if (url === '/preview') return response(200, '{"ready":false}');
      calls.push({ url, options, body: JSON.parse(options.body) });
      const reply = replies.shift();
      if (reply instanceof Error) throw reply;
      return reply;
    },
  });
  return { confirm, previous, feedback, status, calls, window,
    async click() { confirm.listeners.click(); await flush(); } };
}

test('HTML 500 is a server failure, never a network failure', async () => {
  const ui = harness([response(500, '<h1>Internal error</h1>')]);
  await ui.click();
  assert.match(ui.feedback.innerHTML, /HTTP 500/);
  assert.doesNotMatch(ui.feedback.innerHTML, /Falha de rede|Internal error/);
  assert.equal(ui.confirm.disabled, false);
  assert.equal(ui.calls[0].options.headers['X-CSRFToken'], 'test-csrf');
});

test('malformed success response is not reported as network failure or success', async () => {
  const ui = harness([response(200, '<html>unexpected</html>')]);
  await ui.click();
  assert.match(ui.feedback.innerHTML, /Resposta inv/);
  assert.doesNotMatch(ui.feedback.innerHTML, /Falha de rede/);
  assert.equal(ui.window.location.href, undefined);
});

test('CSRF HTML rejection and login redirect have distinct feedback', async () => {
  for (const [reply, expected] of [
    [response(403, '<html>Forbidden</html>'), /HTTP 403/],
    [response(200, '<html>Login</html>', true), /sess.*expirou/],
  ]) {
    const ui = harness([reply]);
    await ui.click();
    assert.match(ui.feedback.innerHTML, expected);
    assert.doesNotMatch(ui.feedback.innerHTML, /Falha de rede/);
  }
});

test('real transport failure retains the confirmation ID on retry', async () => {
  const ui = harness([new TypeError('Failed to fetch'), response(200, '{"ok":true,"continuar":false}')]);
  await ui.click();
  assert.match(ui.feedback.innerHTML, /Falha de rede/);
  assert.equal(ui.confirm.disabled, false);
  await ui.click();
  assert.equal(ui.calls.length, 2);
  assert.equal(ui.calls[0].body.request_id, ui.calls[1].body.request_id);
  assert.deepEqual(ui.calls[0].body.acoes, ui.calls[1].body.acoes);
  assert.equal(ui.window.location.href, '/sheet?levelup=ok');
});

test('validation messages remain escaped and are not converted into success', async () => {
  const ui = harness([response(400, '{"ok":false,"erros":["Invalid <choice>"]}')]);
  await ui.click();
  assert.match(ui.feedback.innerHTML, /Invalid &lt;choice&gt;/);
  assert.equal(ui.confirm.disabled, false);
  assert.equal(ui.window.location.href, undefined);
});

test('successful dependent choices keep the continuation controls', async () => {
  const ui = harness([response(200, '{"ok":true,"continuar":true,"continuar_pendencias":true}')]);
  await ui.click();
  assert.match(ui.feedback.innerHTML, /Resolver escolhas restantes/);
  assert.equal(ui.confirm.hidden, true);
  assert.equal(ui.previous.hidden, true);
});
