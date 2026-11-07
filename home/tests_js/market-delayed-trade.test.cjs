const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '..', 'static/js/mercado_loja.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

function harness() {
  const listeners = new Map();
  const requests = [];
  const events = [];
  const wallet = { textContent: '10 PO' };
  const sale = { innerHTML: 'inventory A' };
  const store = { innerHTML: 'templates A' };
  const feedback = { classList: { toggle(name, value) { feedback[name] = value; } } };
  const pickerForm = { addEventListener() {} };
  const picker = {
    value: 'A', selectedOptions: [{ textContent: 'Character A' }],
    closest: () => pickerForm,
    addEventListener(type, fn) { listeners.set(`picker:${type}`, fn); },
  };
  const fields = {
    '[data-shop-personagem]': picker, '[data-shop-carteira]': wallet,
    '[data-shop-venda]': sale, '[data-shop-feedback]': feedback, '.mkt-store': store,
  };
  const root = {
    dataset: {}, querySelector: key => fields[key] || null, querySelectorAll: () => [],
    addEventListener(type, fn) {
      const callbacks = listeners.get(type) || [];
      callbacks.push(fn);
      listeners.set(type, callbacks);
    },
    dispatchEvent(event) { events.push(event.type); },
  };
  const document = {
    querySelector: () => root,
    contains: form => form.connected,
    body: { contains: button => button.connected },
  };
  const history = { state: {}, replaceState(state) { this.state = state; }, pushState(state) { this.state = state; } };
  const context = {
    document, history, URL,
    window: { location: { href: 'https://example.invalid/market/' }, addEventListener() {},
      matchMedia: () => ({ matches: false, addEventListener() {} }) },
    CustomEvent: class { constructor(type) { this.type = type; } },
    FormData: class { constructor(form) { this.form = form; } get() { return 'test-csrf'; } },
    DOMParser: class {
      parseFromString(id) {
        const next = {
          '[data-shop-personagem]': { value: id, selectedOptions: [{ textContent: `Character ${id}` }] },
          '[data-shop-carteira]': { textContent: `wallet ${id}` },
          '[data-shop-venda]': { innerHTML: `inventory ${id}` },
          '.mkt-store': { innerHTML: `templates ${id}` },
        };
        return { querySelector: () => ({ querySelector: key => next[key] }) };
      }
    },
    fetch(url, options) {
      return new Promise((resolve, reject) => requests.push({ url, options, resolve, reject }));
    },
  };
  vm.runInNewContext(source, context);
  function submit(selling = false) {
    const button = { connected: true, disabled: false, getAttribute: () => 'Test item' };
    const form = {
      connected: true, action: `/character/${picker.value}/${selling ? 'sell' : 'buy'}/`,
      hasAttribute: key => selling && key === 'data-shop-sell', querySelector: () => button,
      reportValidity: () => true,
      closest: key => key === 'form[data-shop-buy], form[data-shop-sell]' ? form : null,
    };
    for (const fn of listeners.get('submit')) fn({ target: form, preventDefault() {} });
    return { form, button };
  }
  function beginSwitch(id) {
    picker.value = id;
    listeners.get('picker:change')();
    return requests.at(-1);
  }
  async function switchTo(id) {
    beginSwitch(id).resolve({ ok: true, text: async () => id });
    await flush();
    picker.selectedOptions = [{ textContent: `Character ${id}` }];
  }
  async function respond(request, data) {
    request.resolve({ json: async () => data });
    await flush();
  }
  return { submit, beginSwitch, switchTo, respond, requests, wallet, sale, feedback, events, picker };
}

const success = { ok: true, carteira_display: '9 PO', venda_html: 'inventory A after trade', credito_display: '1 PO' };

test('delayed success for A does not overwrite B or report a failed transaction', async () => {
  const h = harness();
  const { button } = h.submit();
  const request = h.requests[0];
  assert.equal(request.url, '/character/A/buy/');
  assert.equal(request.options.method, 'POST');
  assert.equal(request.options.credentials, 'same-origin');
  assert.equal(request.options.headers['X-CSRFToken'], 'test-csrf');
  await h.switchTo('B');
  await h.respond(request, success);
  assert.equal(h.wallet.textContent, 'wallet B');
  assert.equal(h.sale.innerHTML, 'inventory B');
  assert.equal(h.events.includes('shop:wallet-changed'), false);
  assert.equal(h.feedback['is-ok'], true);
  assert.match(h.feedback.textContent, /Character A/);
  assert.match(h.feedback.textContent, /Comprado:/);
  assert.equal(button.disabled, false);
});

test('A -> B -> A is a new context even when the ID matches', async () => {
  const h = harness();
  h.submit(true);
  const request = h.requests[0];
  await h.switchTo('B');
  await h.switchTo('A');
  await h.respond(request, success);
  assert.equal(h.wallet.textContent, 'wallet A');
  assert.equal(h.sale.innerHTML, 'inventory A');
  assert.match(h.feedback.textContent, /Vendido:/);
  assert.equal(h.feedback['is-ok'], true);
});

test('overlapping character requests and a pending switch reject old trade snapshots', async () => {
  const h = harness();
  h.submit();
  const trade = h.requests[0];
  const b = h.beginSwitch('B');
  const a = h.beginSwitch('A');
  await h.respond(trade, success);
  assert.equal(h.wallet.textContent, '10 PO');
  assert.equal(h.sale.innerHTML, 'inventory A');
  a.resolve({ ok: true, text: async () => 'A' });
  await flush();
  b.resolve({ ok: true, text: async () => 'B' });
  await flush();
  assert.equal(h.picker.value, 'A');
  assert.equal(h.wallet.textContent, 'wallet A');
});

test('concurrent trades are gated until settlement, including across character switches', async () => {
  const h = harness();
  h.submit();
  h.submit(true);
  assert.equal(h.requests.length, 1);
  await h.switchTo('B');
  h.submit();
  assert.equal(h.requests.length, 2, 'only the first trade and character GET may be sent');
  await h.respond(h.requests[0], success);
  h.submit();
  assert.equal(h.requests.length, 3);
  await h.respond(h.requests[2], { ...success, carteira_display: 'wallet B after trade' });
  assert.equal(h.wallet.textContent, 'wallet B after trade');
});

test('current-context success preserves wallet, inventory, event and messages', async () => {
  for (const selling of [false, true]) {
    const h = harness();
    const { button } = h.submit(selling);
    await h.respond(h.requests[0], success);
    assert.equal(h.wallet.textContent, '9 PO');
    assert.equal(h.sale.innerHTML, success.venda_html);
    assert.equal(h.events.filter(type => type === 'shop:wallet-changed').length, 1);
    assert.equal(h.feedback.textContent, selling
      ? 'Vendido: Test item por 1 PO. Carteira: 9 PO'
      : 'Comprado: Test item. Carteira: 9 PO');
    assert.equal(button.disabled, false);
  }
});

test('business failures and unconfirmed network results release the gate with accurate messages', async () => {
  for (const network of [false, true]) {
    const h = harness();
    const { button } = h.submit();
    if (network) { h.requests[0].reject(new Error('offline')); await flush(); }
    else await h.respond(h.requests[0], { ok: false, msg: 'saldo' });
    assert.equal(h.wallet.textContent, '10 PO');
    assert.equal(h.sale.innerHTML, 'inventory A');
    assert.equal(h.feedback['is-err'], true);
    assert.match(h.feedback.textContent, network ? /Falha de rede/ : /Saldo insuficiente/);
    if (network) {
      assert.equal(h.feedback.textContent,
        'Falha de rede: resultado não confirmado. Consulte a carteira e o histórico antes de repetir o negócio.');
      assert.doesNotMatch(h.feedback.textContent, /não foi concluído|não foi possível concluir/i);
    }
    assert.equal(button.disabled, false);
    h.submit();
    assert.equal(h.requests.length, 2);
  }
});

test('a lost response after switching characters identifies the unconfirmed transaction', async () => {
  const h = harness();
  h.submit();
  await h.switchTo('B');
  h.requests[0].reject(new Error('response lost'));
  await flush();
  assert.match(h.feedback.textContent, /Personagem: Character A/);
  assert.match(h.feedback.textContent, /resultado não confirmado/);
  assert.match(h.feedback.textContent, /Consulte a carteira e o histórico antes de repetir/);
  assert.doesNotMatch(h.feedback.textContent, /não foi concluído|não foi possível concluir/i);
  assert.equal(h.wallet.textContent, 'wallet B');
  assert.equal(h.sale.innerHTML, 'inventory B');
});

test('late business errors identify their character and never mutate the current snapshot', async () => {
  const h = harness();
  h.submit();
  await h.switchTo('B');
  await h.respond(h.requests[0], { ok: false, msg: 'saldo' });
  assert.equal(h.wallet.textContent, 'wallet B');
  assert.equal(h.sale.innerHTML, 'inventory B');
  assert.match(h.feedback.textContent, /Character A/);
  assert.match(h.feedback.textContent, /Saldo insuficiente/);
});

test('a failed character switch still invalidates the old trade snapshot', async () => {
  const h = harness();
  h.submit();
  h.beginSwitch('B').reject(new Error('offline'));
  await flush();
  assert.equal(h.picker.value, 'A');
  await h.respond(h.requests[0], success);
  assert.equal(h.wallet.textContent, '10 PO');
  assert.equal(h.sale.innerHTML, 'inventory A');
  assert.equal(h.feedback['is-ok'], true);
  assert.match(h.feedback.textContent, /Character A/);
});

test('a rendering error after confirmed success is not reported as a failed trade', async () => {
  const h = harness();
  const { button } = h.submit();
  Object.defineProperty(h.sale, 'innerHTML', {
    get: () => 'inventory A', set() { throw new Error('render failed'); },
  });
  await h.respond(h.requests[0], success);
  assert.equal(h.feedback['is-ok'], true);
  assert.equal(h.feedback['is-err'], false);
  assert.match(h.feedback.textContent, /Comprado:/);
  assert.match(h.feedback.textContent, /Recarregue/);
  assert.doesNotMatch(h.feedback.textContent, /Falha de rede/);
  assert.equal(button.disabled, false);
  h.submit();
  assert.equal(h.requests.length, 2);
});

test('invalid JSON preserves the generic failure without mutating the snapshot', async () => {
  const h = harness();
  const { button } = h.submit();
  h.requests[0].resolve({ json: async () => { throw new Error('invalid JSON'); } });
  await flush();
  assert.equal(h.feedback.textContent, 'Não foi possível concluir o negócio.');
  assert.equal(h.feedback['is-err'], true);
  assert.equal(h.wallet.textContent, '10 PO');
  assert.equal(h.sale.innerHTML, 'inventory A');
  assert.equal(button.disabled, false);
});
