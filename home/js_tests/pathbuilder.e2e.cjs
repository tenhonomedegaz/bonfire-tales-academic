/* Navegador real contra StaticLiveServerTestCase. Não simula nem intercepta a API. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE || 'playwright');

const origin = process.env.PATHBUILDER_E2E_URL;
const sessionName = process.env.PATHBUILDER_E2E_COOKIE_NAME;
const sessionValue = process.env.PATHBUILDER_E2E_COOKIE_VALUE;
const base = JSON.parse(process.env.PATHBUILDER_E2E_BASE || '{}');
const builds = JSON.parse(process.env.PATHBUILDER_E2E_BUILDS || '[]');
const laboratory = `${origin}/sistemas/pathbuilder/laboratorio/`;

if (!origin || !sessionName || !sessionValue || !base.classe || builds.length !== 2) {
  throw new Error('Ambiente E2E incompleto.');
}

function fingerprint(value) {
  return JSON.stringify([value.nome, value.classe, value.raca, value.linhagem,
    value.essencia, value.antecedente, value.scores]);
}

async function waitPreview(page, previousCount) {
  await page.waitForFunction(count => window.__pbPreviewCount > count, previousCount);
  await page.waitForFunction(() => !document.querySelector('#pb-status').textContent.includes('Derivando'));
  await page.locator('#pb-folha [data-pb-folha]').waitFor();
  assert.equal(await page.locator('.pb-sheet-error').count(), 0, 'prévia real aceita pelo cliente');
  const response = await page.evaluate(() => window.__pbLastPreview);
  assert.equal(response.ok, true, JSON.stringify(response.erros));
  return response.build;
}

async function previewAfter(page, action) {
  const previousCount = await page.evaluate(() => window.__pbPreviewCount);
  await action();
  return waitPreview(page, previousCount);
}

async function stored(page) {
  return page.evaluate(() => JSON.parse(localStorage.getItem('bonfire:pathbuilder:builds')));
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.setDefaultTimeout(15000);
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', route => {
    if (route.request().url().startsWith(origin)) return route.continue();
    return route.abort();
  });
  await context.addCookies([{ name: sessionName, value: sessionValue, url: origin }]);
  await context.addInitScript(({ initialBase, initialBuilds, initialFingerprint }) => {
    if (!localStorage.getItem('bonfire:pathbuilder:base')) {
      localStorage.setItem('bonfire:pathbuilder:base', JSON.stringify(initialBase));
      localStorage.setItem('bonfire:pathbuilder:base_fp', JSON.stringify(initialFingerprint));
      localStorage.setItem('bonfire:pathbuilder:builds', JSON.stringify(initialBuilds));
    }
    window.__pbPreviewCount = Number(sessionStorage.getItem('bonfire:pathbuilder:e2e-previews') || 0);
    const originalFetch = window.fetch;
    window.fetch = function (...args) {
      const url = String(args[0]);
      return originalFetch.apply(this, args).then(async response => {
        if (url.includes('/sistemas/pathbuilder/preview/')) {
          window.__pbLastPreview = await response.clone().json();
          window.__pbPreviewCount += 1;
          sessionStorage.setItem('bonfire:pathbuilder:e2e-previews', String(window.__pbPreviewCount));
        }
        return response;
      });
    };
  }, { initialBase: base, initialBuilds: builds, initialFingerprint: fingerprint(base) });

  try {
    await page.goto(laboratory, { waitUntil: 'load' });
    await waitPreview(page, 0);
    assert.match(await page.locator('#pb-status').innerText(), /Nível 4/);

    await page.locator('[data-step-tab="3"]').click();
    await previewAfter(page, () =>
      page.locator('[data-opt-slug="resiliente"] [data-opt-pick]').click());
    await previewAfter(page, () =>
      page.locator('[data-talent-attr="resiliente"]').selectOption('DES'));

    await page.locator('[data-step-tab="2"]').click();
    const resilientChoice = page.locator('[data-choice-key*="resiliente"]');
    await resilientChoice.first().waitFor();
    const choiceKey = await resilientChoice.first().getAttribute('data-choice-key');
    assert.ok(choiceKey, 'Resiliente expõe a chave de salvaguarda');
    const selectedPreview = await previewAfter(page, () => page.evaluate(key => {
      // Cada clique refaz os cartões: use os elementos atuais, não nós desconectados.
      const values = Array.from(document.querySelectorAll('[data-choice-key]'))
        .filter(card => card.dataset.choiceKey === key).map(card => card.dataset.choiceVal);
      values.forEach(value => {
        const card = Array.from(document.querySelectorAll('[data-choice-key]'))
          .find(row => row.dataset.choiceKey === key && row.dataset.choiceVal === value);
        card.querySelector('[data-choice-pick]').click();
      });
    }, choiceKey));
    let current = await stored(page);
    assert.equal(current[0].escolhas[choiceKey].length, 1, 'rajada mantém uma salvaguarda');
    assert.deepEqual(selectedPreview.escolhas_grupos.find(group => group.key === choiceKey)
      .resolvidas.map(row => row.valor), current[0].escolhas[choiceKey]);

    await page.locator('[data-step-tab="3"]').click();
    const removedPreview = await previewAfter(page, () =>
      page.locator('[data-opt-slug="resiliente"] [data-opt-pick]').click());
    current = await stored(page);
    assert.deepEqual(current[0].talentos, []);
    assert.equal(current[0].escolhas[choiceKey], undefined, 'remoção limpa subescolha');
    assert.equal(removedPreview.escolhas_grupos.some(group => group.key === choiceKey), false);

    await previewAfter(page, () =>
      page.locator('[data-opt-slug="resiliente"] [data-opt-pick]').click());
    await previewAfter(page, () =>
      page.locator('[data-talent-attr="resiliente"]').selectOption('DES'));
    await page.locator('[data-step-tab="2"]').click();
    await resilientChoice.first().waitFor();
    current = await stored(page);
    assert.equal(current[0].escolhas[choiceKey], undefined, 'recolocar não restaura seleção');

    await previewAfter(page, () =>
      resilientChoice.first().locator('[data-choice-pick]').click());
    const selectedBeforeReload = (await stored(page))[0].escolhas[choiceKey];
    assert.equal(selectedBeforeReload.length, 1);
    const reloadedPreview = await previewAfter(page, () => page.reload({ waitUntil: 'load' }));
    assert.deepEqual((await stored(page))[0].escolhas[choiceKey], selectedBeforeReload);
    assert.deepEqual(reloadedPreview.escolhas_grupos.find(group => group.key === choiceKey)
      .resolvidas.map(row => row.valor), selectedBeforeReload);

    await page.locator('[data-step-tab="3"]').click();
    await previewAfter(page, () =>
      page.locator('[data-opt-slug="resiliente"] [data-opt-pick]').click());
    const burstPreview = await previewAfter(page, () => page.evaluate(() => {
      for (let attempt = 0; attempt < 10; attempt += 1) {
        ['FOR', 'DES', 'CON', 'INT', 'SAB', 'CAR'].forEach(sig => {
          document.querySelector(`[data-attr="${sig}"][data-delta="1"]`).click();
        });
      }
    }));
    current = await stored(page);
    const points = Object.values(current[0].atributos_bonus).reduce((sum, value) => sum + value, 0);
    assert.equal(points, burstPreview.orcamento.asi_slots * 2, 'rajada respeita orçamento real');
    assert.equal(burstPreview.orcamento.pontos_restantes, 0);
    assert.equal(await page.locator('#pb-attributes .pb-attr').count(), 6);
    assert.equal(await page.locator('[data-attr][data-delta="1"]:enabled').count(), 0);
    const consumed = Object.keys(current[0].atributos_bonus).find(sig => current[0].atributos_bonus[sig] > 0);
    await previewAfter(page, () => page.locator(`[data-attr="${consumed}"][data-delta="-1"]`).click());
    assert.equal(await page.locator(`[data-attr="${consumed}"][data-delta="1"]`).isEnabled(), true,
      'orçamento esgotado permite remover e voltar a editar');

    const beforeImport = await stored(page);
    async function uploadBundle(bundle) {
      await page.evaluate(() => { document.querySelector('#pb-status').textContent = ''; });
      await page.locator('#pb-import').setInputFiles({
        name: 'build-bonfire.json', mimeType: 'application/json',
        buffer: Buffer.from(JSON.stringify(bundle))
      });
    }
    await uploadBundle({ base: 'base inválida', builds: beforeImport });
    await page.waitForFunction(() => document.querySelector('#pb-status').textContent.includes('Arquivo de Pathbuilder inválido'));
    assert.match(await page.locator('#pb-status').innerText(), /Arquivo de Pathbuilder inválido/);
    assert.deepEqual(await stored(page), beforeImport, 'base inválida conserva a edição');
    await uploadBundle({ base, builds: [{ ...beforeImport[0], classes: [null] }, beforeImport[1]] });
    await page.waitForFunction(() => document.querySelector('#pb-status').textContent.includes('Arquivo de Pathbuilder inválido'));
    assert.match(await page.locator('#pb-status').innerText(), /Arquivo de Pathbuilder inválido/);
    assert.deepEqual(await stored(page), beforeImport, 'classe inválida conserva a edição');

    const foreignClass = [{ slug: 'classe-de-outra-base', nivel: 1, subclasse: '' }];
    await uploadBundle({ base, builds: [beforeImport[0], { ...beforeImport[1], classes: foreignClass }] });
    await page.waitForFunction(() => document.querySelector('#pb-status').textContent.includes('Arquivo de Pathbuilder'));
    assert.deepEqual(await stored(page), beforeImport, 'foreign class preserves both variants');

    for (const invalidHeader of [
      { formato: 'outro-editor', versao: 1 },
      { formato: 'bonfire-pathbuilder', versao: 2 },
    ]) {
      await uploadBundle({ ...invalidHeader, base, builds: beforeImport });
      await page.waitForFunction(() => document.querySelector('#pb-status').textContent.includes('Arquivo de Pathbuilder'));
      assert.deepEqual(await stored(page), beforeImport, 'unsupported file preserves editing');
    }

    for (const [label, invalidBuild] of [
      ['fractional level', { ...beforeImport[0], classes: [
        { ...beforeImport[0].classes[0], nivel: 1.5 },
        ...beforeImport[0].classes.slice(1)] }],
      ['boolean bonus', { ...beforeImport[0], atributos_bonus: { FOR: true } }],
      ['fractional quantity', { ...beforeImport[0], itens: [
        { tipo: 'mundano', slug: 'corda', qtd: 1.5 }] }],
      ['talents object', { ...beforeImport[0], talentos: { slug: 'resiliente' } }],
      ['choices array', { ...beforeImport[0], escolhas: [] }],
      ['invalid choice values', { ...beforeImport[0], escolhas: { afinidade: 'fogo' } }],
      ['spells object', { ...beforeImport[0], magias: { slug: 'luz' } }],
      ['invalid item row', { ...beforeImport[0], itens: [null] }],
    ]) {
      await uploadBundle({ base, builds: [invalidBuild, beforeImport[1]] });
      await page.waitForFunction(() => document.querySelector('#pb-status').textContent.includes('Arquivo de Pathbuilder'));
      assert.match(await page.locator('#pb-status').innerText(), /Arquivo de Pathbuilder inv/);
      assert.deepEqual(await stored(page), beforeImport, `${label} preserves editing`);
    }

    const imported = [{ ...beforeImport[0], atributos_bonus: {} }, beforeImport[1]];
    assert.ok(imported.every(build => Array.isArray(build.classes) &&
      build.classes.every(row => row && typeof row.slug === 'string')),
    JSON.stringify(imported.map(build => build.classes)));
    try {
      await previewAfter(page, () => uploadBundle({ base, builds: imported }));
    } catch (error) {
      throw new Error(`${error.message}; import status=${await page.locator('#pb-status').innerText()}; JS=${errors.join(' | ')}`);
    }
    assert.deepEqual((await stored(page))[0].atributos_bonus, {},
      'arquivo válido ainda substitui a build e atualiza a prévia');

    const beforeSaved = await stored(page);
    await page.evaluate(({ currentBase, validBuilds }) => {
      const broken = JSON.parse(JSON.stringify(validBuilds));
      broken[0].classes[0].nivel = 1.5;
      localStorage.setItem('bonfire:pathbuilder:saved', JSON.stringify([
        { id: 'broken', nome: 'Versão inválida', base: currentBase, builds: broken },
        { id: 'working', nome: 'Versão válida', base: currentBase, builds: validBuilds }
      ]));
    }, { currentBase: base, validBuilds: beforeImport });
    await previewAfter(page, () => page.reload({ waitUntil: 'load' }));
    await page.locator('#pb-saved-builds').selectOption('broken');
    assert.match(await page.locator('#pb-status').innerText(), /Arquivo de Pathbuilder inválido/);
    assert.deepEqual(await stored(page), beforeSaved, 'versão local inválida conserva a edição');
    await page.evaluate(({ currentBase, validBuilds }) => {
      localStorage.setItem('bonfire:pathbuilder:saved', JSON.stringify([
        { id: 'broken-choice', nome: 'Invalid choices', base: currentBase,
          builds: [{ ...validBuilds[0], escolhas: { afinidade: 'fogo' } }, validBuilds[1]] }
      ]));
    }, { currentBase: base, validBuilds: beforeImport });
    await previewAfter(page, () => page.reload({ waitUntil: 'load' }));
    await page.locator('#pb-saved-builds').selectOption('broken-choice');
    assert.match(await page.locator('#pb-status').innerText(), /Arquivo de Pathbuilder/);
    assert.deepEqual(await stored(page), beforeSaved, 'invalid saved choices preserve editing');
    await page.evaluate(({ currentBase, validBuilds, foreignClass }) => {
      localStorage.setItem('bonfire:pathbuilder:saved', JSON.stringify([
        { id: 'foreign', nome: 'Foreign class', base: currentBase,
          builds: [validBuilds[0], { ...validBuilds[1], classes: foreignClass }] },
        { id: 'working', nome: 'Working version', base: currentBase, builds: validBuilds }
      ]));
    }, { currentBase: base, validBuilds: beforeImport, foreignClass });
    await previewAfter(page, () => page.reload({ waitUntil: 'load' }));
    await page.locator('#pb-saved-builds').selectOption('foreign');
    assert.match(await page.locator('#pb-status').innerText(), /Arquivo de Pathbuilder/);
    assert.deepEqual(await stored(page), beforeSaved, 'foreign saved version preserves editing');
    await previewAfter(page, () => page.locator('#pb-saved-builds').selectOption('working'));
    assert.deepEqual(await stored(page), beforeImport, 'versão local válida restaura a edição');

    if (process.env.BONFIRE_ARTIFACT_DIR) {
      fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR, { recursive: true });
      await page.locator('[data-step-tab="3"]').click();
      await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR, 'e2e-pathbuilder.png'), fullPage: true });
      await page.setViewportSize({ width: 360, height: 800 });
      assert.equal(await page.locator('#pb-attributes .pb-attr').count(), 6);
      await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR, 'e2e-pathbuilder-mobile.png'), fullPage: true });
    }
    assert.deepEqual(errors, [], 'sem erros JavaScript');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
