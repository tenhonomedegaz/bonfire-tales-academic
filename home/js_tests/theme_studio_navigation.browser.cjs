const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE || 'playwright');

const script = fs.readFileSync(path.join(__dirname, '../static/js/theme-studio.js'), 'utf8');
const keys = ['forja-de-brasas', 'aurora-glacial', 'circulo-arcano'];
const names = ['Forja de Brasas', 'Aurora Glacial', 'Círculo Arcano'];
const choices = keys.map((key, index) =>
  `<a href="?tema=${key}" data-theme-choice="${key}" class="${index === 0 ? 'is-selected' : ''}" ${index === 0 ? 'aria-current="true"' : ''}><strong>${names[index]}</strong></a>`).join('');
const products = keys.map((key, index) =>
  `<section data-theme-product="${key}" ${index === 0 ? '' : 'hidden'}>${names[index]}</section>`).join('');

test('ateliê restaura a coleção escolhida com Voltar e Avançar', async t => {
  const server = http.createServer((request, response) => {
    response.setHeader('Content-Type', 'text/html; charset=utf-8');
    response.end(`<main class="ts-page">${choices}${products}<p data-preview-note role="status"></p></main><script>${script}</script>`);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH } : {}) });
  t.after(() => browser.close());
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const base = `http://127.0.0.1:${server.address().port}/atelie/`;
  await page.goto(base);
  await page.locator('[data-theme-choice="aurora-glacial"]').focus();
  await page.keyboard.press('Enter');
  assert.equal(new URL(page.url()).searchParams.get('tema'), 'aurora-glacial');
  assert.equal(await page.locator('[data-theme-product]:visible').count(), 1);
  assert.equal(await page.locator('[data-theme-product]:visible').getAttribute('data-theme-product'), 'aurora-glacial');
  assert.match(await page.locator('[data-preview-note]').innerText(), /Aurora Glacial/);
  await page.locator('[data-theme-choice="circulo-arcano"]').click();
  assert.equal(new URL(page.url()).searchParams.get('tema'), 'circulo-arcano');
  await page.goBack();
  assert.equal(await page.locator('[data-theme-product]:visible').getAttribute('data-theme-product'), 'aurora-glacial');
  assert.equal(await page.locator('[aria-current="true"]').getAttribute('data-theme-choice'), 'aurora-glacial');
  await page.goBack();
  assert.equal(await page.locator('[data-theme-product]:visible').getAttribute('data-theme-product'), 'forja-de-brasas');
  await page.goForward();
  assert.equal(await page.locator('[data-theme-product]:visible').getAttribute('data-theme-product'), 'aurora-glacial');
  assert.deepEqual(errors, []);
});
