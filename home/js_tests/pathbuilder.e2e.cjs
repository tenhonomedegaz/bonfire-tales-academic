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
