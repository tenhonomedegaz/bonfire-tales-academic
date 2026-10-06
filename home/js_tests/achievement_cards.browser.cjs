/* Cartões reais do template Django, abertos em Chromium sem banco. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const renderScript = `
import json, os
from datetime import datetime, timezone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
import django
django.setup()
from django.template.loader import render_to_string
items = [
    {'nome': 'Primeira Centelha', 'descricao': 'Criou uma ficha & começou a jogar.',
     'obtida': True, 'icone_url': '', 'concedida_em': datetime(2026, 10, 6, tzinfo=timezone.utc)},
    {'nome': 'Caminho do Herói', 'descricao': 'Complete a primeira aventura.',
     'obtida': False, 'progresso_aventuras': {'atual': 0, 'alvo': 1, 'operador': 'gte'}},
]
print(json.dumps([render_to_string('home/partials/_conquista_item.html', {'c': item}) for item in items]))
`;

test('detalhes de conquistas abrem por toque e teclado sem estourar a tela', async t => {
  const python = process.env.BONFIRE_PYTHON || path.join(root, '.venv/Scripts/python.exe');
  const rendered = spawnSync(python, ['-c', renderScript], { cwd: root, encoding: 'utf8' });
  assert.equal(rendered.status, 0, rendered.stderr);
  const cards = JSON.parse(rendered.stdout);
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH } : {}) });
  t.after(() => browser.close());
  const page = await browser.newPage({ viewport: { width: 360, height: 800 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setContent(`<html lang="pt-BR"><meta charset="utf-8"><style>
    :root { --pf-accent:#d2aa67; --pf-gold:#d2aa67; --stroke:#635747;
      --bg0:#221d19; --text:#f4eee6; --muted:#c5b9ab; }
    body { background:#171311; color:var(--text); font-family:Arial,sans-serif;
      padding:1rem; margin:0; box-sizing:border-box; }
    * { box-sizing:border-box; }
    </style><ul class="conquista-grid">${cards.join('')}</ul>`);
  await page.addStyleTag({ content: fs.readFileSync(path.join(root, 'home/static/css/pages/perfil.css'), 'utf8') });
  const achieved = page.locator('.conquista-item.is-obtida');
  const locked = page.locator('.conquista-item.is-bloqueada');
  assert.equal(await achieved.locator('.conquista-info-body').isVisible(), false);
  await achieved.locator('summary').click();
  assert.equal(await achieved.locator('.conquista-info-body').isVisible(), true);
  assert.match(await achieved.innerText(), /Criou uma ficha & começou a jogar/);
  assert.match(await achieved.innerText(), /Obtida em 06\/10\/2026/);
  await locked.locator('summary').focus();
  await page.keyboard.press('Enter');
  assert.equal(await locked.locator('.conquista-info-body').isVisible(), true);
  assert.match(await locked.innerText(), /0 comprovadas/);
  for (const width of [360, 768, 1280, 1920]) {
    await page.setViewportSize({ width, height: 800 });
    const layout = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth, width: innerWidth,
      cards: [...document.querySelectorAll('.conquista-item')].map(el => el.getBoundingClientRect().right),
    }));
    assert.ok(layout.scroll <= layout.width, `sem rolagem horizontal em ${width}px`);
    assert.ok(layout.cards.every(right => right <= width), `cartões cabem em ${width}px`);
    if (process.env.BONFIRE_ARTIFACT_DIR) {
      fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR, { recursive: true });
      await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR,
        `achievement-cards-${width}.png`), fullPage: true });
    }
  }
  await page.setViewportSize({ width: 360, height: 800 });
  await page.evaluate(() => { document.body.style.zoom = '2'; });
  const zoom = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth, width: innerWidth,
  }));
  assert.ok(zoom.scroll <= zoom.width, 'sem rolagem horizontal a 200% em 360px');
  assert.deepEqual(errors, []);
});
