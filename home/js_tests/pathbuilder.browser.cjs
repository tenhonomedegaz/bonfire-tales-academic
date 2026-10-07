/* Cliente real + template real; respostas HTTP controladas, sem banco.
 * BONFIRE_PLAYWRIGHT_MODULE aponta para uma instalação existente de playwright/core.
 * node --test home/js_tests/pathbuilder.browser.cjs
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '..');
const base = { nome: 'Q14', classe: 'guerreiro', raca: 'anao', scores: {
  FOR: 8, DES: 14, CON: 13, INT: 15, SAB: 10, CAR: 12,
} };
const seed = () => ({ modo: 'regras', classes: [{ slug: 'guerreiro', nivel: 4, subclasse: '' }],
  atributos_bonus: {}, escolhas: {}, talentos: [], talentos_raciais: [], itens: [], magias: [] });
const catalogs = { classes: [{ slug: 'guerreiro', nome: 'Guerreiro', subclasses: [] },
  { slug: 'mago', nome: 'Mago', subclasses: [] }, { slug: 'clerigo', nome: 'Clérigo', subclasses: [] }],
  talentos: [{ slug: 'resiliente', nome: 'Resiliente', grupo: 'Geral', atributos: ['CON'] }],
  itens_mundanos: [], itens_magicos: [], magias: [
    { slug: 'luz', nome: 'Luz', nivel: 0 }, { slug: 'curar-ferimentos', nome: 'Curar Ferimentos', nivel: 1 },
    { slug: 'escudo', nome: 'Escudo', nome_ingles: 'Shield', nivel: 1 },
  ] };
const template = fs.readFileSync(path.join(root, 'templates/home/pages/pathbuilder.html'), 'utf8');
const content = template.split('{% block content %}')[1].split('{% endblock %}')[0]
  .replace(/\{%[\s\S]*?%\}|\{#[\s\S]*?#\}|\{\{[\s\S]*?\}\}/g, '')
  .replace(/<script>[\s\S]*?<\/script>/g, '');
const html = `<!doctype html><html lang="pt-BR"><meta charset="utf-8">
  <link rel="stylesheet" href="/style.css"><body>${content}
  <script type="application/json" id="pb-catalogs">${JSON.stringify(catalogs)}</script>
  <script>window.PATHBUILDER_PREVIEW_URL='/preview';window.CSRF_TOKEN='test';</script>
  <script src="/client.js"></script></body></html>`;

function result(build, marker = 'confirmada') {
  const points = Object.values(build.atributos_bonus).reduce((sum, value) => sum + value, 0);
  const slots = build.classes[0].nivel >= 4 ? 1 : 0;
  return { ok: true, build: { nivel: build.classes[0].nivel,
    orcamento: { asi_slots: slots, pontos_restantes: (slots - build.talentos.length) * 2 - points },
    atributos: Object.entries(base.scores).map(([sig, value]) => ({ sig,
      valor: value + (build.atributos_bonus[sig] || 0), mod: 0 })),
    atributos_pathbuilder_aplicados: build.atributos_bonus,
    escolhas_grupos: [], escolhas_pendentes: [], talentos_raciais_grupos: [],
    validacao: { modo: build.modo, valida: true, problemas: [] },
    ficha_html: `<p data-confirmed-sheet>${marker}</p>` } };
}

async function harness(t, builds = [seed(), seed()]) {
  const requests = [];
  const server = http.createServer((req, res) => {
    if (req.url === '/preview') {
      let body = '';
      req.on('data', data => { body += data; });
      req.on('end', () => requests.push({ input: JSON.parse(body), fail() {
        // Interrompe depois dos headers: o Chromium não repete a conexão silenciosamente.
        res.writeHead(200, { 'Content-Type': 'application/json', 'Content-Length': '1000' });
        res.write('{"ok":', () => res.destroy());
      },
        reply(data, status = 200) {
          res.writeHead(status, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ...data,
            request_id: data.request_id === undefined ? JSON.parse(body).request_id : data.request_id }));
        } }));
    } else if (req.url === '/client.js') {
      res.setHeader('Content-Type', 'text/javascript');
      res.end(fs.readFileSync(process.env.BONFIRE_PATHBUILDER_JS || path.join(root, 'static/js/pathbuilder.js')));
    } else if (req.url === '/style.css') {
      res.setHeader('Content-Type', 'text/css');
      res.end(['base', 'responsive', 'ficha', 'pathbuilder'].map(name =>
        fs.readFileSync(path.join(root, `static/css/pages/${name}.css`), 'utf8')).join('\n'));
    } else { res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(html); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH } : {}) });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  t.after(async () => {
    await browser.close();
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    assert.deepEqual(errors, [], 'sem erros JavaScript no navegador');
  });
  await context.addInitScript(({ base, builds }) => {
    if (localStorage.getItem('bonfire:pathbuilder:base')) return;
    localStorage.setItem('bonfire:pathbuilder:base', JSON.stringify(base));
    localStorage.setItem('bonfire:pathbuilder:base_fp', JSON.stringify(JSON.stringify([
      base.nome, base.classe, base.raca, base.linhagem, base.essencia, base.antecedente, base.scores,
    ])));
    localStorage.setItem('bonfire:pathbuilder:builds', JSON.stringify(builds));
  }, { base, builds });
  await page.goto(`http://127.0.0.1:${server.address().port}/`, { waitUntil: 'load' });
  async function nextRequest(index) {
    for (let attempt = 0; attempt < 100; attempt++) {
      if (requests[index]) return requests[index];
      await new Promise(resolve => setTimeout(resolve, 20));
    }
    throw new Error(`preview ${index} não recebido`);
  }
  async function initial() {
    const request = await nextRequest(0);
    request.reply(result(request.input.build));
    await page.locator('[data-confirmed-sheet]').waitFor();
    await page.locator('[data-step-tab="3"]').click();
  }
  const stored = () => page.evaluate(() => JSON.parse(localStorage.getItem('bonfire:pathbuilder:builds')));
  return { page, requests, nextRequest, initial, stored };
}

test('falha HTTP mantém ficha e orçamento; rajada não distribui 60/2 pontos', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  const request = await h.nextRequest(1);
  request.reply({ ok: false, erros: ['Falha controlada'] }, 500);
  await h.page.locator('#pb-status.is-error').waitFor();
  assert.equal(await h.page.locator('[data-confirmed-sheet]').count(), 1);
  assert.match(await h.page.locator('#pb-asi-counter').innerText(), /1\/2/);
  const bar = await h.page.locator('.pb-sheet-bar').boundingBox();
  const notice = await h.page.locator('.pb-sheet-error').boundingBox();
  assert.ok(bar.y + bar.height <= notice.y, 'cabeçalho não cobre o aviso de erro');
  await h.page.evaluate(() => {
    for (let n = 0; n < 10; n++) {
      document.querySelectorAll('[data-attr][data-delta="1"]').forEach(button => button.click());
    }
  });
  const [build] = await h.stored();
  assert.equal(Object.values(build.atributos_bonus).reduce((a, b) => a + b, 0), 2);
  if (process.env.BONFIRE_ARTIFACT_DIR) {
    fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR, { recursive: true });
    await h.page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR, 'q14-desktop.png'), fullPage: true });
    await h.page.setViewportSize({ width: 360, height: 800 });
    const mobileBar = await h.page.locator('.pb-sheet-bar').boundingBox();
    const mobileNotice = await h.page.locator('.pb-sheet-error').boundingBox();
    assert.ok(mobileBar.y + mobileBar.height <= mobileNotice.y);
    await h.page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR, 'q14-mobile.png'), fullPage: true });
  }
});

test('erro inicial não habilita ASI/talentos, mas permite corrigir a progressão', async t => {
  const h = await harness(t);
  (await h.nextRequest(0)).reply({ ok: false, erros: ['Falha inicial'] }, 500);
  await h.page.locator('#pb-status.is-error').waitFor();
  await h.page.locator('[data-step-tab="3"]').click();
  await h.page.evaluate(() => {
    document.querySelector('[data-attr="FOR"][data-delta="1"]').click();
    document.querySelector('[data-opt-slug="resiliente"] [data-opt-pick]').click();
  });
  const [build] = await h.stored();
  assert.deepEqual(build.atributos_bonus, {});
  assert.deepEqual(build.talentos, []);
  await h.page.locator('[data-step-tab="1"]').click();
  await h.page.locator('[data-class-level="0"][data-delta="-1"]').click();
  assert.equal((await h.stored())[0].classes[0].nivel, 3);
});

test('resposta de edição anterior é ignorada já durante o debounce', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  const old = await h.nextRequest(1);
  await h.page.locator('[data-attr="DES"][data-delta="1"]').click();
  old.reply(result(old.input.build, 'OBSOLETA'));
  await h.page.waitForTimeout(120);
  assert.doesNotMatch(await h.page.locator('#pb-folha').innerText(), /OBSOLETA/);
  const current = await h.nextRequest(2);
  current.reply(result(current.input.build, 'ATUAL'));
  await h.page.getByText('ATUAL', { exact: true }).waitFor();
});

test('reduzir nível não reutiliza orçamento alto após erro; remoção continua possível', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  const valid = await h.nextRequest(1);
  valid.reply(result(valid.input.build));
  await h.page.waitForFunction(() => !document.querySelector('#pb-status').textContent.includes('Derivando'));
  await h.page.locator('[data-step-tab="1"]').click();
  await h.page.locator('[data-class-level="0"][data-delta="-1"]').click();
  (await h.nextRequest(2)).reply({ ok: false, erros: ['Falha após nível'] }, 500);
  await h.page.locator('#pb-status.is-error').waitFor();
  await h.page.locator('[data-step-tab="3"]').click();
  assert.equal(await h.page.locator('[data-attr="DES"][data-delta="1"]').isDisabled(), true);
  await h.page.locator('[data-attr="FOR"][data-delta="-1"]').click();
  assert.equal((await h.stored())[0].atributos_bonus.FOR, 0);
});

test('resposta incompleta e queda de rede mantêm dados; edição seguinte recupera a prévia', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  (await h.nextRequest(1)).reply({ ok: true, build: {} });
  await h.page.locator('#pb-status.is-error').waitFor();
  assert.equal(await h.page.locator('[data-confirmed-sheet]').count(), 1);
  await h.page.locator('[data-attr="DES"][data-delta="1"]').click();
  const failed = await h.nextRequest(2);
  failed.fail();
  await h.page.locator('#pb-status.is-error').waitFor();
  assert.equal(await h.page.locator('[data-confirmed-sheet]').count(), 1);
  assert.equal((await h.stored())[0].atributos_bonus.DES, 1);
  await h.page.locator('[data-attr="DES"][data-delta="-1"]').click();
  const recovery = await h.nextRequest(3);
  recovery.reply(result(recovery.input.build, 'RECUPERADA'));
  await h.page.getByText('RECUPERADA', { exact: true }).waitFor();
  assert.equal(await h.page.locator('#pb-status.is-error').count(), 0);
});

test('troca A/B descarta respostas em voo e revalida a variante editada ao retornar', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  const pendingA = await h.nextRequest(1);
  await h.page.locator('[data-build-tab="1"]').click();
  const requestB = await h.nextRequest(2);
  requestB.reply(result(requestB.input.build, 'FICHA B'));
  await h.page.getByText('FICHA B', { exact: true }).waitFor();
  pendingA.reply(result(pendingA.input.build, 'A ANTIGA'));
  await h.page.locator('[data-build-tab="0"]').click();
  const requestA = await h.nextRequest(3);
  requestA.reply(result(requestA.input.build, 'FICHA A ATUAL'));
  await h.page.getByText('FICHA A ATUAL', { exact: true }).waitFor();
  const builds = await h.stored();
  assert.equal(builds[0].atributos_bonus.FOR, 1);
  assert.deepEqual(builds[1].atributos_bonus, {});
});

test('reload preserva a edição e aguarda novo orçamento autoritativo', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  const old = await h.nextRequest(1);
  old.reply({ ok: false, erros: ['Falha antes de recarregar'] }, 500);
  await h.page.locator('#pb-status.is-error').waitFor();
  await h.page.reload();
  const reload = await h.nextRequest(2);
  assert.equal(reload.input.build.atributos_bonus.FOR, 1);
  await h.page.locator('[data-step-tab="3"]').click();
  assert.equal(await h.page.locator('[data-attr="DES"][data-delta="1"]').isDisabled(), true);
  reload.reply(result(reload.input.build, 'RECARREGADA'));
  await h.page.getByText('RECARREGADA', { exact: true }).waitFor();
  assert.equal(await h.page.locator('[data-attr="DES"][data-delta="1"]').isDisabled(), false);
});

test('resposta de outra solicitação não substitui a ficha válida', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  const pending = await h.nextRequest(1);
  pending.reply({ ...result(pending.input.build, 'FICHA ERRADA'), request_id: 'outro-pedido' });
  await h.page.locator('#pb-status.is-error').waitFor();
  assert.equal(await h.page.getByText('FICHA ERRADA', { exact: true }).count(), 0);
  assert.equal(await h.page.locator('[data-confirmed-sheet]').count(), 1);
  assert.equal((await h.stored())[0].atributos_bonus.FOR, 1);
  await h.page.locator('#pb-retry-preview').click();
  const retry = await h.nextRequest(2);
  retry.reply(result(retry.input.build, 'FICHA CORRIGIDA'));
  await h.page.getByText('FICHA CORRIGIDA', { exact: true }).waitFor();
});

test('edição com armazenamento local cheio avisa e sobrevive ao reload da sessão', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.evaluate(() => {
    window.__savedSetItem = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (this === localStorage && key === 'bonfire:pathbuilder:builds') {
        throw new DOMException('local full', 'QuotaExceededError');
      }
      return window.__savedSetItem.call(this, key, value);
    };
  });
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  await h.page.getByText('Edição guardada só nesta sessão.', { exact: false }).waitFor();
  assert.equal((await h.stored())[0].atributos_bonus.FOR, undefined);
  assert.equal(await h.page.evaluate(() => JSON.parse(sessionStorage.getItem('bonfire:pathbuilder:builds'))[0].atributos_bonus.FOR), 1);
  const edit = await h.nextRequest(1);
  edit.reply(result(edit.input.build));
  await h.page.reload();
  const request = await h.nextRequest(2);
  assert.equal(request.input.build.atributos_bonus.FOR, 1);
  request.reply(result(request.input.build));
});

test('cópia local recupera edição quando a sessão bloqueia escrita e leitura', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.evaluate(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (this === sessionStorage && key === 'bonfire:pathbuilder:builds') {
        throw new DOMException('session blocked', 'SecurityError');
      }
      return original.call(this, key, value);
    };
  });
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  assert.equal((await h.stored())[0].atributos_bonus.FOR, 1);
  const edit = await h.nextRequest(1);
  edit.reply(result(edit.input.build));
  await h.page.context().addInitScript(() => {
    const original = Storage.prototype.getItem;
    Storage.prototype.getItem = function (key) {
      if (this === sessionStorage && key.startsWith('bonfire:pathbuilder:')) {
        throw new DOMException('session blocked', 'SecurityError');
      }
      return original.call(this, key);
    };
  });
  await h.page.reload();
  const reload = await h.nextRequest(2);
  assert.equal(reload.input.build.atributos_bonus.FOR, 1);
  reload.reply(result(reload.input.build));
  await h.page.locator('[data-confirmed-sheet]').waitFor();
});

test('importa duas builds pela cópia local quando a sessão falha e preserva edição se ambos falham', async t => {
  const h = await harness(t);
  await h.initial();
  const importedBase = { ...base, nome: 'Importada localmente' };
  const importedBuilds = [seed(), { ...seed(), classes: [{ slug: 'guerreiro', nivel: 3, subclasse: '' }] }];
  await h.page.evaluate(() => {
    window.__savedSetItem = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (this === sessionStorage && key === 'bonfire:pathbuilder:base') {
        throw new DOMException('session full', 'QuotaExceededError');
      }
      return window.__savedSetItem.call(this, key, value);
    };
  });
  const upload = async (name, builds) => h.page.locator('#pb-import').setInputFiles({
    name: 'builds.json', mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify({ formato: 'bonfire-pathbuilder', versao: 1,
      base: { ...base, nome: name }, builds })),
  });
  await upload(importedBase.nome, importedBuilds);
  for (const index of [1, 2]) {
    const request = await h.nextRequest(index);
    request.reply(result(request.input.build));
  }
  await h.page.waitForFunction(() => JSON.parse(localStorage.getItem('bonfire:pathbuilder:base')).nome === 'Importada localmente');
  assert.equal(await h.page.locator('#pb-status.is-error').count(), 0);
  assert.equal((await h.stored())[1].classes[0].nivel, 3);
  assert.equal(await h.page.evaluate(() => sessionStorage.getItem('bonfire:pathbuilder:base')), null);
  await h.page.reload();
  const reload = await h.nextRequest(3);
  assert.equal(reload.input.base.nome, importedBase.nome);
  assert.equal(reload.input.build.classes[0].nivel, 4);
  reload.reply(result(reload.input.build));
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.evaluate(() => {
    window.__savedSetItem = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (key === 'bonfire:pathbuilder:base') {
        throw new DOMException('both full', 'QuotaExceededError');
      }
      return window.__savedSetItem.call(this, key, value);
    };
  });
  await upload('Não importada', importedBuilds);
  for (const index of [4, 5]) {
    const request = await h.nextRequest(index);
    request.reply(result(request.input.build));
  }
  await h.page.locator('#pb-status.is-error').waitFor();
  assert.match(await h.page.locator('#pb-status').innerText(), /Não foi possível guardar/);
  assert.equal(await h.page.evaluate(() => JSON.parse(localStorage.getItem('bonfire:pathbuilder:base')).nome), importedBase.nome);
  assert.equal(await h.page.locator('[data-confirmed-sheet]').count(), 1);
});

test('importação rejeita atributo desconhecido sem trocar as builds e aceita correção', async t => {
  const h = await harness(t);
  await h.initial();
  const upload = async builds => h.page.locator('#pb-import').setInputFiles({
    name: 'atributos.json', mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify({ formato: 'bonfire-pathbuilder', versao: 1,
      base, builds })),
  });
  const original = await h.stored();
  const other = { ...seed(), classes: [{ slug: 'guerreiro', nivel: 3, subclasse: '' }] };
  await upload([seed(), { ...other, atributos_bonus: { FOR: 1, AGI: 2 } }]);
  await h.page.locator('#pb-status.is-error').waitFor();
  assert.match(await h.page.locator('#pb-status').innerText(), /inválido/);
  assert.deepEqual(await h.stored(), original);
  assert.equal(h.requests.length, 1);

  await upload([seed(), { ...other, atributos_bonus: { FOR: 1 } }]);
  for (const index of [1, 2]) {
    const request = await h.nextRequest(index);
    request.reply(result(request.input.build));
  }
  await h.page.waitForFunction(() => {
    const rows = JSON.parse(localStorage.getItem('bonfire:pathbuilder:builds'));
    return rows[1].atributos_bonus.FOR === 1 && rows[1].classes[0].nivel === 3;
  });
  assert.equal(await h.page.locator('#pb-status.is-error').count(), 0);
});

test('versão salva abre as duas builds; exclusão cancelada, confirmada ou falha preserva a edição', async t => {
  const second = { ...seed(), classes: [{ slug: 'guerreiro', nivel: 3, subclasse: '' }] };
  const h = await harness(t, [seed(), second]);
  await h.initial();
  const saved = () => h.page.evaluate(() => JSON.parse(localStorage.getItem('bonfire:pathbuilder:saved')));
  h.page.once('dialog', dialog => dialog.accept('Versão original'));
  await h.page.locator('#pb-save').click();
  const original = (await saved())[0];
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  const edited = await h.nextRequest(1);
  edited.reply(result(edited.input.build));
  await h.page.waitForFunction(() => !document.querySelector('#pb-status').textContent.includes('Derivando'));

  h.page.once('dialog', dialog => dialog.dismiss());
  await h.page.locator('#pb-delete-save').click();
  assert.equal((await saved())[0].id, original.id);
  assert.equal(await h.page.locator('#pb-saved-builds').inputValue(), original.id);
  assert.equal((await h.stored())[0].atributos_bonus.FOR, 1);

  await h.page.locator('#pb-saved-builds').selectOption('');
  await h.page.locator('#pb-saved-builds').selectOption(original.id);
  const pendingA = await h.nextRequest(2);
  const pendingB = await h.nextRequest(3);
  h.page.once('dialog', dialog => dialog.accept());
  await h.page.locator('#pb-delete-save').click();
  pendingA.reply(result(pendingA.input.build));
  pendingB.reply(result(pendingB.input.build));
  await h.page.waitForTimeout(100);
  assert.deepEqual(await saved(), []);
  assert.equal((await h.stored())[0].atributos_bonus.FOR, 1,
    'prévia atrasada não restaura a cópia excluída');
  assert.equal((await h.stored())[1].classes[0].nivel, 3);
  await h.page.reload();
  const reload = await h.nextRequest(4);
  assert.equal(reload.input.build.atributos_bonus.FOR, 1);
  reload.reply(result(reload.input.build));
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  assert.equal(await h.page.locator('#pb-saved-builds option').count(), 1);

  await h.page.locator('[data-step-tab="3"]').click();
  h.page.once('dialog', dialog => dialog.accept('Versão para reabrir'));
  await h.page.locator('#pb-save').click();
  const reopen = (await saved())[0];
  await h.page.locator('[data-attr="DES"][data-delta="1"]').click();
  const editedAgain = await h.nextRequest(5);
  editedAgain.reply(result(editedAgain.input.build));
  await h.page.locator('#pb-saved-builds').selectOption('');
  await h.page.locator('#pb-saved-builds').selectOption(reopen.id);
  for (const index of [6, 7]) {
    const request = await h.nextRequest(index);
    request.reply(result(request.input.build));
  }
  await h.page.waitForFunction(() => JSON.parse(localStorage.getItem('bonfire:pathbuilder:builds'))[0].atributos_bonus.DES === undefined);
  assert.equal((await h.stored())[1].classes[0].nivel, 3);

  await h.page.evaluate(() => {
    window.__savedSetItem = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (key === 'bonfire:pathbuilder:saved') throw new DOMException('full', 'QuotaExceededError');
      return window.__savedSetItem.call(this, key, value);
    };
  });
  h.page.once('dialog', dialog => dialog.accept());
  await h.page.locator('#pb-delete-save').click();
  assert.equal((await saved())[0].id, reopen.id, 'falha de armazenamento conserva a cópia');
  await h.page.evaluate(() => { Storage.prototype.setItem = window.__savedSetItem; });
  h.page.once('dialog', dialog => dialog.accept());
  await h.page.locator('#pb-delete-save').click();
  assert.deepEqual(await saved(), []);
  assert.equal((await h.stored())[0].atributos_bonus.FOR, 1);
});

test('JSON corrompido na sessão usa a cópia local e permite continuar a edição', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  const edit = await h.nextRequest(1);
  edit.reply(result(edit.input.build));
  await h.page.evaluate(() => {
    for (const key of ['base', 'base_fp', 'builds']) {
      sessionStorage.setItem(`bonfire:pathbuilder:${key}`, '{corrompido');
    }
  });
  await h.page.reload();
  const reload = await h.nextRequest(2);
  assert.equal(reload.input.base.classe, 'guerreiro');
  assert.equal(reload.input.build.atributos_bonus.FOR, 1);
  reload.reply(result(reload.input.build, 'RECUPERADA'));
  await h.page.getByText('RECUPERADA', { exact: true }).waitFor();
  await h.page.locator('[data-step-tab="3"]').click();
  await h.page.locator('[data-attr="DES"][data-delta="1"]').click();
  const continued = await h.nextRequest(3);
  assert.equal(continued.input.build.atributos_bonus.FOR, 1);
  assert.equal(continued.input.build.atributos_bonus.DES, 1);
  continued.reply(result(continued.input.build));
  assert.equal((await h.stored())[0].atributos_bonus.DES, 1);
});

test('edição sem armazenamento avisa e continua exportável', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.evaluate(() => {
    window.__savedSetItem = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (key === 'bonfire:pathbuilder:builds') {
        throw new DOMException('full', 'QuotaExceededError');
      }
      return window.__savedSetItem.call(this, key, value);
    };
  });
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  await h.page.getByText('Não foi possível guardar a edição.', { exact: false }).waitFor();
  const downloadPromise = h.page.waitForEvent('download');
  await h.page.locator('#pb-export').click();
  const download = await downloadPromise;
  const bundle = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
  assert.equal(bundle.builds[0].atributos_bonus.FOR, 1);
  assert.equal((await h.stored())[0].atributos_bonus.FOR, undefined);
});

test('reset invalida orçamento, ficha e consultas da construção anterior', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  const old = await h.nextRequest(1);
  h.page.once('dialog', dialog => dialog.accept());
  await h.page.locator('#pb-reset').click();
  const reset = await h.nextRequest(2);
  assert.equal(await h.page.locator('[data-confirmed-sheet]').count(), 0);
  assert.equal(await h.page.locator('[data-attr="DES"][data-delta="1"]').isDisabled(), true);
  old.reply(result(old.input.build, 'ANTES DO RESET'));
  reset.reply(result(reset.input.build, 'NOVA BASE'));
  await h.page.getByText('NOVA BASE', { exact: true }).waitFor();
  assert.equal((await h.stored())[0].classes[0].nivel, 1);
  assert.deepEqual((await h.stored())[0].atributos_bonus, {});
  assert.equal(await h.page.locator('[data-attr="DES"][data-delta="1"]').isDisabled(), true);
});

test('cancelar ações destrutivas preserva as duas builds; confirmar clona e zera', async t => {
  const a = { ...seed(), atributos_bonus: { FOR: 1 } };
  const b = { ...seed(), atributos_bonus: { DES: 1 } };
  const h = await harness(t, [a, b]);
  await h.initial();
  const before = await h.stored();
  h.page.once('dialog', dialog => dialog.dismiss());
  await h.page.locator('#pb-clone').click();
  h.page.once('dialog', dialog => dialog.dismiss());
  await h.page.locator('#pb-reset').click();
  assert.deepEqual(await h.stored(), before);
  assert.equal(h.requests.length, 1, 'cancelar não solicita nova prévia');

  h.page.once('dialog', dialog => dialog.accept());
  await h.page.locator('#pb-clone').click();
  const clonedA = await h.nextRequest(1);
  const clonedB = await h.nextRequest(2);
  assert.deepEqual(clonedB.input.build, clonedA.input.build);
  clonedA.reply(result(clonedA.input.build));
  clonedB.reply(result(clonedB.input.build));
  assert.deepEqual((await h.stored())[1], (await h.stored())[0]);

  h.page.once('dialog', dialog => dialog.accept());
  await h.page.locator('#pb-reset').click();
  const reset = await h.nextRequest(3);
  assert.deepEqual((await h.stored()).map(build => build.atributos_bonus), [{}, {}]);
  reset.reply(result(reset.input.build));
});

test('Q12 atributo elegivel do talento persiste e retirar a origem limpa a escolha', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.locator('[data-step-tab="3"]').click();
  await h.page.locator('[data-opt-slug="resiliente"] [data-opt-pick]').click();
  const added = await h.nextRequest(1);
  added.reply(result(added.input.build));
  const select = h.page.locator('[data-talent-attr="resiliente"]');
  assert.deepEqual(await select.locator('option').evaluateAll(rows => rows.map(row => row.value)), ['', 'CON']);
  await select.selectOption('CON');
  const selected = await h.nextRequest(2);
  assert.deepEqual(selected.input.build.talentos, [{ slug: 'resiliente', atributo: 'CON' }]);
  selected.reply(result(selected.input.build));
  await h.page.locator('[data-opt-slug="resiliente"] [data-opt-pick]').click();
  const removed = await h.nextRequest(3);
  assert.deepEqual(removed.input.build.talentos, []);
  assert.equal(await select.count(), 0);
  removed.reply(result(removed.input.build));
});

test('Q09 recusa de talento explica orçamento sem apagar a build', async t => {
  const h = await harness(t);
  const first = await h.nextRequest(0);
  const initial = result(first.input.build);
  initial.build.orcamento.asi_slots = 0;
  first.reply(initial);
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.locator('[data-step-tab="3"]').click();
  const talent = h.page.locator('[data-picker="talento"] [data-opt-pick]').first();
  await talent.click();
  assert.match(await h.page.locator('#pb-action-feedback').innerText(), /Sem slot de ASI/);
  assert.equal((await h.stored())[0].talentos.length, 0);
});

test('escolhas cheias explicam recusa; marco racial pendente aparece na etapa e bloqueia revisão', async t => {
  const h = await harness(t);
  const key = 'opcao|teste|0|teste|0';
  const group = { key, label: 'Estilo', origem: 'Teste', limite: 1, pendentes: 1,
    resolvidas: [], selecionadas: [], opcoes: [
      { valor: 'defesa', nome: 'Defesa' }, { valor: 'duelo', nome: 'Duelo' },
    ] };
  const preview = (build, pendingChoice) => {
    const answer = result(build);
    answer.build.escolhas_grupos = [{ ...group, pendentes: pendingChoice ? 1 : 0,
      selecionadas: build.escolhas[key] || [] }];
    answer.build.escolhas_pendentes = pendingChoice ? [{ pendentes: 1 }] : [];
    answer.build.talentos_raciais_grupos = [{ nivel: 5, opcoes: [{ nome: 'Vigor' }],
      selecionado: build.talentos_raciais[0]?.nome || '' }];
    answer.build.validacao = { modo: 'regras', valida: false,
      problemas: ['Escolha um talento racial.'] };
    return answer;
  };
  const first = await h.nextRequest(0);
  first.reply(preview(first.input.build, true));
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.locator('[data-step-tab="2"]').click();
  assert.equal(await h.page.locator('[data-step-tab="2"] .pb-step-badge').getAttribute('data-pending'), '1');
  assert.equal(await h.page.locator('[data-step-tab="3"] .pb-step-badge').getAttribute('data-pending'), '2');
  await h.page.locator('[data-choice-val="defesa"] [data-choice-pick]').click();
  const selected = await h.nextRequest(1);
  selected.reply(preview(selected.input.build, false));
  await h.page.waitForFunction(() => document.querySelector('[data-step-tab="2"] .pb-step-badge').dataset.pending === '');
  await h.page.locator('[data-choice-val="duelo"] [data-choice-pick]').click();
  assert.match(await h.page.locator('#pb-choice-feedback').innerText(), /Todas as escolhas de Estilo/);
  assert.deepEqual((await h.stored())[0].escolhas[key], ['defesa']);
  await h.page.locator('[data-step-tab="6"]').click();
  assert.equal(await h.page.locator('#pb-conclude').isDisabled(), true);
  await h.page.setViewportSize({ width: 360, height: 800 });
  await h.page.locator('[data-step-tab="3"]').click();
  assert.equal(await h.page.locator('[data-step-tab="3"] .pb-step-badge').getAttribute('data-pending'), '2');
  assert.equal(await h.page.locator('[data-racial-level="5"]').isVisible(), true);
  await h.page.locator('[data-racial-level="5"]').selectOption('Vigor');
  const racial = await h.nextRequest(2);
  assert.deepEqual(racial.input.build.talentos_raciais, [{ nivel: 5, nome: 'Vigor' }]);
  racial.reply(preview(racial.input.build, false));
  await h.page.waitForFunction(() => document.querySelector('[data-step-tab="3"] .pb-step-badge').dataset.pending === '1');
});

test('erro inicial permite repetir a prévia sem alterar nem perder a build', async t => {
  const h = await harness(t);
  const initial = await h.nextRequest(0);
  initial.reply({ ok: false, erros: ['Falha temporária'] }, 500);
  await h.page.locator('#pb-status.is-error').waitFor();
  const before = await h.stored();
  await h.page.setViewportSize({ width: 360, height: 800 });
  const retryButton = await h.page.locator('#pb-retry-preview').boundingBox();
  const sheet = await h.page.locator('#pb-sheet').boundingBox();
  assert.ok(retryButton.x >= sheet.x && retryButton.x + retryButton.width <= sheet.x + sheet.width,
    'tentar novamente cabe no painel da ficha no celular');
  await h.page.locator('#pb-retry-preview').click();
  const retry = await h.nextRequest(1);
  assert.deepEqual(retry.input.build, before[0]);
  assert.equal(await h.page.locator('#pb-retry-preview').isHidden(), true);
  retry.reply(result(retry.input.build, 'RECUPERADA SEM EDIÇÃO'));
  await h.page.getByText('RECUPERADA SEM EDIÇÃO', { exact: true }).waitFor();
  assert.equal(await h.page.locator('#pb-status.is-error').count(), 0);
  assert.deepEqual(await h.stored(), before);
  await h.page.locator('[data-step-tab="3"]').click();
  assert.equal(await h.page.locator('[data-attr="FOR"][data-delta="1"]').isDisabled(), false);
});

test('prévia antiga não autoriza nova escolha após mudar o nível, mas permite remover', async t => {
  const key = 'opcao|teste|0|marco-nivel-quatro|0';
  const build = seed();
  build.escolhas[key] = ['defesa'];
  const h = await harness(t, [build, seed()]);
  const group = { key, label: 'Marco de nível quatro', origem: 'Marco', limite: 2,
    pendentes: 0, resolvidas: [], selecionadas: ['defesa'], opcoes: [
      { valor: 'defesa', nome: 'Defesa' }, { valor: 'duelo', nome: 'Duelo' },
    ] };
  const first = await h.nextRequest(0);
  const initial = result(first.input.build);
  initial.build.escolhas_grupos = [group];
  first.reply(initial);
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.locator('[data-step-tab="1"]').click();
  await h.page.locator('[data-class-level="0"][data-delta="-1"]').click();
  (await h.nextRequest(1)).reply({ ok: false, erros: ['Falha temporária'] }, 500);
  await h.page.locator('#pb-status.is-error').waitFor();
  await h.page.locator('[data-step-tab="2"]').click();
  await h.page.locator('[data-choice-val="duelo"] [data-choice-pick]').click();
  assert.deepEqual((await h.stored())[0].escolhas[key], ['defesa']);
  assert.match(await h.page.locator('#pb-choice-feedback').innerText(), /prévia atualizada/);
  await h.page.locator('[data-choice-val="defesa"] [data-choice-pick]').click();
  assert.deepEqual((await h.stored())[0].escolhas[key], []);
  const reduced = await h.nextRequest(2);
  reduced.reply(result(reduced.input.build));
  await h.page.waitForFunction(() => !document.querySelector('#pb-status').textContent.includes('Derivando'));
  await h.page.locator('[data-step-tab="1"]').click();
  await h.page.locator('[data-class-level="0"][data-delta="1"]').click();
  const restored = await h.nextRequest(3);
  const restoredResult = result(restored.input.build);
  restoredResult.build.escolhas_grupos = [{ ...group, selecionadas: [] }];
  restored.reply(restoredResult);
  await h.page.locator('[data-step-tab="2"]').click();
  await h.page.locator('[data-choice-val="duelo"] [data-choice-pick]').click();
  assert.deepEqual((await h.stored())[0].escolhas[key], ['duelo']);
});

test('repetir prévia após erro mantém a última ficha até confirmar a mesma edição', async t => {
  const h = await harness(t);
  await h.initial();
  await h.page.locator('[data-attr="FOR"][data-delta="1"]').click();
  (await h.nextRequest(1)).reply({ ok: false, erros: ['Falha temporária'] }, 500);
  await h.page.locator('#pb-status.is-error').waitFor();
  assert.equal(await h.page.locator('[data-confirmed-sheet]').count(), 1);
  const before = await h.stored();
  await h.page.locator('#pb-retry-preview').click();
  const retry = await h.nextRequest(2);
  assert.deepEqual(retry.input.build, before[0]);
  assert.equal(await h.page.locator('[data-confirmed-sheet]').count(), 1);
  retry.reply(result(retry.input.build, 'EDIÇÃO CONFIRMADA'));
  await h.page.getByText('EDIÇÃO CONFIRMADA', { exact: true }).waitFor();
  assert.deepEqual(await h.stored(), before);
  assert.equal(await h.page.locator('#pb-retry-preview').isHidden(), true);
});

test('talento racial indisponível é pendência e pode ser substituído ou limpo', async t => {
  const build = seed();
  build.talentos_raciais = [{ nivel: 5, nome: 'Legado' }];
  const h = await harness(t, [build, seed()]);
  const preview = (input, groups) => {
    const answer = result(input);
    answer.build.orcamento.pontos_restantes = 0;
    answer.build.talentos_raciais_grupos = groups;
    answer.build.validacao = { modo: 'regras', valida: !groups.length && !input.talentos_raciais.length,
      problemas: input.talentos_raciais.length ? ['Talento racial indisponível.'] : [] };
    return answer;
  };
  const first = await h.nextRequest(0);
  first.reply(preview(first.input.build, [{ nivel: 5, opcoes: [{ nome: 'Vigor' }] }]));
  await h.page.locator('[data-step-tab="3"]').click();
  assert.equal(await h.page.locator('[data-step-tab="3"] .pb-step-badge').getAttribute('data-pending'), '1');
  assert.match(await h.page.locator('#pb-racial-talents').innerText(), /Legado \(indisponível\)/);
  await h.page.locator('[data-racial-level="5"]').selectOption('Vigor');
  const replaced = await h.nextRequest(1);
  assert.deepEqual(replaced.input.build.talentos_raciais, [{ nivel: 5, nome: 'Vigor' }]);
  replaced.reply(preview(replaced.input.build, []));
  await h.page.waitForFunction(() => document.querySelector('[data-step-tab="3"] .pb-step-badge').dataset.pending === '1');
  assert.match(await h.page.locator('#pb-racial-talents').innerText(), /Vigor \(indisponível\)/);
  await h.page.locator('[data-racial-level="5"]').selectOption('');
  const cleared = await h.nextRequest(2);
  assert.deepEqual(cleared.input.build.talentos_raciais, []);
  cleared.reply(preview(cleared.input.build, []));
  await h.page.waitForFunction(() => document.querySelector('[data-step-tab="3"] .pb-step-badge').dataset.pending === '');
});

test('Q10 magias avança para revisão; pendência e prévia desatualizada não concluem', async t => {
  const build = seed();
  build.magias = [{slug:'luz',preparada:true}];
  const h = await harness(t, [build, seed()]);
  const first = await h.nextRequest(0);
  const invalid = result(first.input.build);
  invalid.build.validacao = {modo:'regras',valida:false,problemas:['Escolha 1 magia concedida de Teste.']};
  first.reply(invalid);
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.locator('[data-step-tab="5"]').click();
  await h.page.locator('[data-step-next]').click();
  assert.equal(await h.page.locator('[data-step="6"]').isVisible(),true);
  assert.equal(await h.page.locator('#pb-conclude').isDisabled(),true);
  assert.match(await h.page.locator('#pb-step-err').innerText(),/Escolha 1 magia/);
  assert.deepEqual((await h.stored())[0].magias,build.magias);
  await h.page.reload();
  assert.equal(await h.page.locator('#pb-conclude').isDisabled(),true);
  const reload = await h.nextRequest(1);
  reload.reply(result(reload.input.build));
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.locator('[data-step-tab="6"]').click();
  await h.page.locator('#pb-conclude').click();
  assert.match(await h.page.locator('#pb-review-status').innerText(),/Simulação concluída/);
  assert.deepEqual((await h.stored())[0].magias,build.magias);
});

test('Q08 ferramenta conhecida bloqueada e seleção editável pode ser retirada', async t => {
  const h = await harness(t);
  const key = 'ferramenta|ferramenta|0|iniciado-artifice|0';
  const group = { key, label: 'Ferramenta', origem: 'Iniciado Artífice', limite: 1,
    resolvidas: [], selecionadas: [], opcoes: [
      { valor: 'ferreiro', nome: 'Ferreiro', ja_proficiente: true },
      { valor: 'carpinteiro', nome: 'Carpinteiro', ja_proficiente: false },
    ] };
  const first = await h.nextRequest(0);
  const initial = result(first.input.build);
  initial.build.escolhas_grupos = [group];
  first.reply(initial);
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.locator('[data-step-tab="2"]').click();
  const known = h.page.locator('[data-choice-val="ferreiro"] [data-choice-pick]');
  assert.equal(await known.isDisabled(), true);
  assert.match(await known.innerText(), /já proficiente/);
  await h.page.locator('[data-choice-val="carpinteiro"] [data-choice-pick]').click();
  const selected = await h.nextRequest(1);
  const next = result(selected.input.build);
  next.build.escolhas_grupos = [{ ...group, selecionadas: ['carpinteiro'],
    resolvidas: [{ valor: 'carpinteiro', nome: 'Carpinteiro' }],
    opcoes: group.opcoes.map(o => ({...o, ja_proficiente:true})) }];
  selected.reply(next);
  await h.page.waitForFunction(() => !document.querySelector('#pb-status').textContent.includes('Derivando'));
  const editable = h.page.locator('[data-choice-val="carpinteiro"] [data-choice-pick]');
  assert.equal(await editable.isDisabled(), false);
  await editable.click();
  assert.deepEqual((await h.stored())[0].escolhas[key], []);
});

test('escolha removida não vira concessão fixa ao falhar prévia; cardinalidade permanece um', async t => {
  const h = await harness(t);
  const key = 'save|save|0|resiliente|0';
  const group = { key, label: 'Resistência', origem: 'Resiliente', limite: 1,
    resolvidas: [], selecionadas: [], opcoes: [
      { valor: 'CON', nome: 'Constituição' }, { valor: 'DES', nome: 'Destreza' },
    ] };
  const first = await h.nextRequest(0);
  const initial = result(first.input.build);
  initial.build.escolhas_grupos = [group];
  first.reply(initial);
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.locator('[data-step-tab="2"]').click();
  await h.page.locator('[data-choice-val="CON"] [data-choice-pick]').click();
  const selected = await h.nextRequest(1);
  const selectedResult = result(selected.input.build);
  selectedResult.build.escolhas_grupos = [{ ...group, selecionadas: ['CON'],
    resolvidas: [{ valor: 'CON', nome: 'Constituição' }] }];
  selected.reply(selectedResult);
  await h.page.waitForFunction(() => !document.querySelector('#pb-status').textContent.includes('Derivando'));
  await h.page.locator('[data-choice-val="CON"] [data-choice-pick]').click();
  (await h.nextRequest(2)).reply({ ok: false, erros: ['Falha após remover'] }, 500);
  await h.page.locator('#pb-status.is-error').waitFor();
  await h.page.evaluate(() => {
    document.querySelector('[data-choice-val="DES"] [data-choice-pick]').click();
    document.querySelector('[data-choice-val="CON"] [data-choice-pick]').click();
  });
  assert.deepEqual((await h.stored())[0].escolhas[key], ['DES']);
});

test('retirar e recolocar Resiliente limpa subescolhas mesmo após erro e reload', async t => {
  const key = 'save_prof|save_prof|0|resiliente|0';
  const unrelated = 'opcao|estilo_de_luta|7|estilo-de-luta|0';
  const build = seed();
  build.talentos = [{ slug: 'resiliente', atributo: 'CON' }];
  build.escolhas = { [key]: ['CON'], [unrelated]: ['defesa'] };
  const h = await harness(t, [build, seed()]);
  const group = { key, origem: 'Resiliente', label: 'Salvaguarda', limite: 1,
    selecionadas: ['CON'], resolvidas: [{ valor: 'CON', nome: 'Constituição' }],
    opcoes: [{ valor: 'CON', nome: 'Constituição' }, { valor: 'DES', nome: 'Destreza' }] };
  const first = await h.nextRequest(0);
  const initial = result(first.input.build);
  initial.build.escolhas_grupos = [group];
  first.reply(initial);
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.locator('[data-step-tab="3"]').click();
  await h.page.locator('[data-opt-slug="resiliente"] [data-opt-pick]').click();
  assert.equal((await h.stored())[0].escolhas[key], undefined);
  assert.deepEqual((await h.stored())[0].escolhas[unrelated], ['defesa']);
  assert.equal(await h.page.locator('[data-choice-key]').count(), 0,
    'prévia anterior não permite editar escolhas do talento removido');
  (await h.nextRequest(1)).reply({ ok: false, erros: ['Erro ao retirar talento'] }, 500);
  await h.page.locator('#pb-status.is-error').waitFor();
  await h.page.locator('[data-opt-slug="resiliente"] [data-opt-pick]').click();
  const replaced = await h.nextRequest(2);
  assert.equal(replaced.input.build.escolhas[key], undefined);
  assert.equal(replaced.input.build.talentos[0].atributo, '');
  const replacement = result(replaced.input.build);
  replacement.build.escolhas_grupos = [{ ...group, selecionadas: [], resolvidas: [] }];
  replaced.reply(replacement);
  await h.page.waitForFunction(() => !document.querySelector('#pb-status').textContent.includes('Derivando'));
  await h.page.locator('[data-step-tab="2"]').click();
  await h.page.locator('[data-choice-val="DES"] [data-choice-pick]').click();
  const selected = await h.nextRequest(3);
  selected.reply({ ok: false, erros: ['Erro antes do reload'] }, 500);
  await h.page.locator('#pb-status.is-error').waitFor();
  await h.page.reload();
  (await h.nextRequest(4)).reply({ ok: false, erros: ['Erro após reload'] }, 500);
  await h.page.locator('#pb-status.is-error').waitFor();
  await h.page.locator('[data-step-tab="3"]').click();
  await h.page.locator('[data-opt-slug="resiliente"] [data-opt-pick]').click();
  assert.equal((await h.stored())[0].escolhas[key], undefined);
  assert.deepEqual((await h.stored())[0].talentos, []);
});

test('Q10 escolhe classe antes de adicionar e aceita a mesma magia em duas classes', async t => {
  const h = await harness(t);
  const first = await h.nextRequest(0);
  const initial = result(first.input.build);
  initial.build.magias_fontes = [
    { slug: 'mago', nome: 'Mago', magias: [] }, { slug: 'clerigo', nome: 'Clérigo', magias: [] },
  ];
  first.reply(initial);
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.locator('[data-step-tab="5"]').click();
  assert.match(await h.page.locator('[data-picker="magia"]').innerText(), /Escolha a classe/);
  await h.page.locator('#pb-spell-class').selectOption('mago');
  await h.page.locator('[data-picker="magia"] [data-opt-slug="luz"] [data-opt-pick]').click();
  await h.page.locator('#pb-spell-class').selectOption('clerigo');
  await h.page.locator('[data-picker="magia"] [data-opt-slug="luz"] [data-opt-pick]').click();
  assert.deepEqual((await h.stored())[0].magias, [
    { slug: 'luz', classe: 'mago', preparada: true },
    { slug: 'luz', classe: 'clerigo', preparada: true },
  ]);
});

test('Q10 preparar magia base cria override sem apagar as demais escolhas', async t => {
  const build = seed();
  build.magias = [{ slug: 'luz', classe: 'mago', preparada: true }];
  const h = await harness(t, [build, seed()]);
  const first = await h.nextRequest(0);
  const initial = result(first.input.build);
  initial.build.magias_fontes = [{ slug: 'mago', nome: 'Mago', magias: [
    { slug: 'luz', nome: 'Luz', nivel: 0, preparada: false },
    { slug: 'curar-ferimentos', nome: 'Curar Ferimentos', nivel: 1, preparada: false },
    { slug: 'escudo', nome: 'Escudo', nivel: 1, preparada: true, sempre_preparada: true },
  ] }];
  first.reply(initial);
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.locator('[data-step-tab="5"]').click();
  const base = h.page.locator('[data-spell-prepared-slug="curar-ferimentos"][data-spell-prepared-class="mago"]');
  assert.equal(await h.page.locator('[data-spell-prepared-slug="escudo"][data-spell-prepared-class="mago"]').isDisabled(), true);
  await base.check();
  assert.deepEqual((await h.stored())[0].magias, [
    { slug: 'luz', classe: 'mago', preparada: true },
    { slug: 'curar-ferimentos', classe: 'mago', preparada: true },
  ]);
  await h.page.locator('[data-remove-spell="1"]').click();
  assert.deepEqual((await h.stored())[0].magias, [{ slug: 'luz', classe: 'mago', preparada: true }]);
  assert.equal(await base.isChecked(), false);
});

test('Q10 linha antiga sem classe continua editável', async t => {
  const build = seed();
  build.magias = [{ slug: 'luz', preparada: true }];
  const h = await harness(t, [build, seed()]);
  const first = await h.nextRequest(0);
  const initial = result(first.input.build);
  initial.build.magias_fontes = [{ slug: 'mago', nome: 'Mago', magias: [] }];
  first.reply(initial);
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.locator('[data-step-tab="5"]').click();
  const source = h.page.locator('[data-spell-class-row="0"]');
  assert.equal(await source.inputValue(), '');
  await source.selectOption('mago');
  assert.deepEqual((await h.stored())[0].magias, [{ slug: 'luz', classe: 'mago', preparada: true }]);
});

test('Q10 remover adição confirmada não a transforma em magia da base', async t => {
  const build = seed();
  build.magias = [{slug:'luz',classe:'mago',preparada:true}];
  const h = await harness(t,[build,seed()]);
  const first = await h.nextRequest(0);
  const initial = result(first.input.build);
  initial.build.magias_fontes = [{slug:'mago',nome:'Mago',magias:[
    {slug:'luz',nome:'Luz',nivel:0,preparada:true,base:false},
    {slug:'escudo',nome:'Escudo',nivel:1,preparada:false,base:true,preparada_base:false}
  ]}];
  first.reply(initial);
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.locator('[data-step-tab="5"]').click();
  assert.equal(await h.page.locator('[data-spell-slug="escudo"]').isDisabled(),true);
  await h.page.locator('[data-remove-spell="0"]').click();
  assert.equal(await h.page.locator('[data-spell-prepared-slug="luz"]').count(),0);
  assert.deepEqual((await h.stored())[0].magias,[]);
});

test('Q01 busca PT/EN sem acentos e teclado preserva magias já escolhidas', async t => {
  const build = seed();
  build.magias = [{ slug: 'luz', classe: 'mago', preparada: true }];
  const h = await harness(t, [build, seed()]);
  const first = await h.nextRequest(0);
  const initial = result(first.input.build);
  initial.build.magias_fontes = [{ slug: 'mago', nome: 'Mago', magias: [] }];
  first.reply(initial);
  await h.page.locator('[data-confirmed-sheet]').waitFor();
  await h.page.locator('[data-step-tab="5"]').click();
  await h.page.locator('#pb-spell-class').selectOption('mago');
  const search = h.page.locator('[data-picker="magia"] [data-picker-search]');
  await search.fill('shield');
  assert.match(await h.page.locator('#pb-spell-results').innerText(), /1 magia.*1 escolha/);
  assert.equal(await h.page.locator('[data-picker="magia"] [data-opt-slug="escudo"]').count(), 1);
  assert.match(await h.page.locator('[data-picker="magia"] [data-opt-slug="escudo"]').innerText(), /Shield/);
  await search.press('ArrowDown');
  assert.equal(await h.page.locator('[data-picker="magia"] [data-opt-slug="escudo"] [data-opt-pick]').evaluate(
    element => element === document.activeElement), true);
  await h.page.keyboard.press('Enter');
  assert.deepEqual((await h.stored())[0].magias, [
    { slug: 'luz', classe: 'mago', preparada: true },
    { slug: 'escudo', classe: 'mago', preparada: true },
  ]);
  await search.fill('inexistente');
  assert.match(await h.page.locator('[data-picker="magia"] [data-picker-list]').innerText(), /Nenhum resultado/);
  assert.match(await h.page.locator('#pb-spell-results').innerText(), /0 magia.*2 escolha/);
  assert.equal(await h.page.locator('#pb-spells [data-spell-prepared-slug]').count(), 2);
});
