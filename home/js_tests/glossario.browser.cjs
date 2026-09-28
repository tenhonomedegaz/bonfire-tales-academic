/* Chromium com o template real e dados controlados; não usa banco.
 * BONFIRE_PLAYWRIGHT_MODULE aponta para uma instalação existente de playwright/core.
 * node --test home/js_tests/glossario.browser.cjs
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/home/pages/glossario.html'), 'utf8');
const baseCss = fs.readFileSync(path.join(root, 'static/css/pages/base.css'), 'utf8');
const responsiveCss = fs.readFileSync(path.join(root, 'static/css/pages/responsive.css'), 'utf8');
const tailwind = fs.readFileSync(path.join(root, 'static/vendor/tailwind/tailwind-3.4.17-typography.js'));
const screenshots = path.resolve(root, '..', 'scratch/evolucao-q17');
const regras = [
  { slug: 'acao-bonus', nome: 'Ação Bônus', nome_en: 'Bonus Action', definicao: 'Uma ação adicional.' },
  { slug: 'vantagem', nome: 'Vantagem', nome_en: 'Advantage', definicao: 'Role dois dados.' },
];
const condicoes = [
  { slug: 'impedido', nome: 'Impedido', nome_en: 'Restrained', definicao: 'Sem movimento.' },
  { slug: 'incapacitado', nome: 'Incapacitado', nome_en: 'Incapacitated', definicao: 'Sem ações.' },
];

function renderCards(source, tag, values) {
  const block = tag === 'c'
    ? /\{% for c in condicoes %\}([\s\S]*?)      \{% endfor %\}(\r?\n    <\/div>)/
    : /\{% for r in regras %\}([\s\S]*?)\{% endfor %\}/;
  return source.replace(block, (...args) => {
    const card = args[1];
    const suffix = tag === 'c' ? args[2] : '';
    return values.map(value => card
    .replace(/\{% for efeito in c\.efeitos_json %\}[\s\S]*?\{% endfor %\}/g, '')
    .replace(new RegExp(`{{ ${tag}\\.slug }}`, 'g'), value.slug)
    .replace(new RegExp(`{{ ${tag}\\.nome\\|lower }}`, 'g'), value.nome.toLowerCase())
    .replace(new RegExp(`{{ ${tag}\\.nome_en\\|lower }}`, 'g'), value.nome_en.toLowerCase())
    .replace(new RegExp(`{{ ${tag}\\.nome }}`, 'g'), value.nome)
    .replace(new RegExp(`{{ ${tag}\\.nome_en }}`, 'g'), value.nome_en)
    .replace(new RegExp(`{{ ${tag}\\.definicao(?:\\|default:${tag}\\.resumo)?\\|escape }}`, 'g'), value.definicao)
    .replace(/\{% if r\.categoria %\}[\s\S]*?\{% endif %\}/g, '')
    .replace(/\{% if c\.nome_en %\}|\{% endif %\}/g, '')).join('') + suffix;
  });
}

function renderTemplate(catalogo) {
  let content = template.split('{% block content %}')[1].split('{% endblock %}')[0];
  content = renderCards(content, 'r', catalogo.regras);
  content = content.replace(/\s*\{% if condicoes %\}([\s\S]*?<\/section>)\r?\n  \{% endif %\}/,
    (_, section) => catalogo.condicoes.length ? section : '');
  if (catalogo.condicoes.length) content = renderCards(content, 'c', catalogo.condicoes);
  const total = catalogo.regras.length + catalogo.condicoes.length;
  content = content
    .replace(/{{ regras\|length\|add:condicoes_count }}/g, String(total))
    .replace(/\{% with condicoes_count=condicoes\|length %\}|\{% endwith %\}/g, '')
    .replace(/\{% url 'mestre_condicoes' %\}/g, '/condicoes/')
    .replace(/\{%[\s\S]*?%\}|\{\{[\s\S]*?\}\}/g, '');
  return `<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/base.css"><link rel="stylesheet" href="/responsive.css"><body><main class="max-w-4xl mx-auto px-3 py-4">${content}</main><script src="/tailwind.js"></script></body></html>`;
}

async function harness(t, catalogo) {
  const server = http.createServer((req, res) => {
    const assets = { '/base.css': ['text/css; charset=utf-8', baseCss], '/responsive.css': ['text/css; charset=utf-8', responsiveCss], '/tailwind.js': ['text/javascript; charset=utf-8', tailwind] };
    if (assets[req.url]) {
      res.setHeader('Content-Type', assets[req.url][0]);
      return res.end(assets[req.url][1]);
    }
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    return res.end(renderTemplate(catalogo));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  t.after(async () => {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
    assert.deepEqual(errors, [], 'sem erros JavaScript no navegador');
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/`, { waitUntil: 'load' });
  return page;
}

async function idsVisiveis(page) {
  return page.locator('.glo-item').evaluateAll(items => items
    .filter(item => !item.classList.contains('hidden')).map(item => item.id));
}

test('pesquisa regras e condições no mesmo índice PT/EN, acentos e maiúsculas', async t => {
  const page = await harness(t, { regras, condicoes });
  const busca = page.getByLabel('Buscar no glossário');
  assert.equal(await page.locator('#glo-count').innerText(), '4');
  assert.equal(await page.locator('#glo-resultados').getAttribute('aria-live'), 'polite');

  await busca.fill('acao');
  assert.deepEqual(await idsVisiveis(page), ['regra-acao-bonus'], 'PT sem acento filtra só regra acentuada');
  await busca.fill('BONUS ACTION');
  assert.deepEqual(await idsVisiveis(page), ['regra-acao-bonus'], 'inglês em maiúsculas filtra só regra');
  await busca.fill('vantagem');
  assert.deepEqual(await idsVisiveis(page), ['regra-vantagem'], 'filtro só regras');
  await busca.fill('RESTRAINED');
  assert.deepEqual(await idsVisiveis(page), ['condicao-impedido'], 'inglês em maiúsculas filtra só condição');
  await busca.fill('impedido');
  assert.deepEqual(await idsVisiveis(page), ['condicao-impedido'], 'filtro só condições');
  await busca.fill('ausente');
  assert.equal(await page.locator('#glo-count').innerText(), '0');
  assert.equal(await page.locator('#glo-vazio').isVisible(), true);
  assert.equal(await page.locator('#glo-condicoes').isVisible(), false);

  await busca.fill('');
  fs.mkdirSync(screenshots, { recursive: true });
  await page.screenshot({ path: path.join(screenshots, 'glossario-1280.png'), fullPage: true });
  await page.setViewportSize({ width: 360, height: 800 });
  await page.screenshot({ path: path.join(screenshots, 'glossario-360.png'), fullPage: true });
});

test('catálogos vazios mostram o estado vazio já no carregamento', async t => {
  const page = await harness(t, { regras: [], condicoes: [] });
  assert.equal(await page.locator('.glo-item').count(), 0);
  assert.equal(await page.locator('#glo-count').innerText(), '0');
  assert.equal(await page.locator('#glo-vazio').isVisible(), true);
  assert.equal(await page.locator('#glo-condicoes').count(), 0);
});
