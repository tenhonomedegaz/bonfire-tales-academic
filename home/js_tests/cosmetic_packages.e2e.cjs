/* Browser check for shipped art and renderer; no server or database required. */
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const root = path.resolve(__dirname, '../static');
const media = path.join(root, 'cosmetics');
const css = path.join(root, 'css/pages/perfil.css');
const chrome = process.env.COSMETIC_CHROME || (
  process.platform === 'win32'
    ? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
    : 'chromium'
);
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'bonfire-cosmetics-'));
const screenshotDir = process.env.COSMETIC_SCREENSHOT_DIR || temp;
fs.mkdirSync(screenshotDir, { recursive: true });

function url(file) {
  return pathToFileURL(path.join(media, file)).href;
}

function layer(slot, file, motion = 'none') {
  return `<div class="cosmetic-layers cosmetic-layers--${slot}" data-cosmetic-layers aria-hidden="true"><img class="cosmetic-layer cosmetic-layer--${motion}" src="${url(file)}" data-fallback="${url(file)}" alt=""></div>`;
}

function card(kind, name) {
  const isArcane = kind === 'arcane';
  return `<section class="public-profile-page theme-${kind}"><div class="public-profile-card">
    <div class="public-profile-banner">${layer('banner', isArcane ? 'arcane-banner.svg' : 'bonfire-banner.svg')}${layer('ornament', isArcane ? 'arcane-ornament.svg' : 'bonfire-ornament.svg', 'float')}</div>
    <div class="public-profile-body"><div class="public-profile-avatar is-packaged"><span>${name[0]}</span>${layer('avatar', isArcane ? 'arcane-ring.svg' : 'ember-ring.svg', 'pulse')}</div>
      <div class="public-profile-main"><div class="public-profile-name-row"><h1>${name}</h1><span class="profile-role">Jogador</span></div><p class="public-profile-handle">@${name.toLowerCase()}</p><p class="public-profile-bio">Histórias, personagens e encontros à luz da fogueira.</p><button class="profile-social-btn" type="button">Seguir</button></div></div>
    </div></section>`;
}

const html = `<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="${pathToFileURL(css).href}">
<style>body{margin:0;padding:24px;background:#0b0e16;color:#f6efe7;font:16px system-ui}main{max-width:1060px;margin:auto}.public-profile-page{--profile-accent:#ef8a42;--profile-accent-2:#cb5541;--profile-surface:#171821;--profile-deep:#10111b;--bg0:#10111b;--bg1:#171821;--text:#f6efe7;--muted:#adacb9;--stroke:#65545a;--ember:#ef8a42;--flame:#cb5541;--spark:#f3be67}.theme-arcane{--profile-accent:#9e97e7;--profile-accent-2:#72cee4}.public-profile-page{margin:0 0 28px}.public-profile-card{min-height:300px}.public-profile-avatar{z-index:2}.public-profile-main{min-width:0}.profile-role{padding:3px 9px;border:1px solid currentColor;border-radius:10px}.profile-social-btn{margin-top:8px;padding:9px 17px;border:1px solid #a98c75;border-radius:8px;color:inherit;background:#302734;cursor:pointer}@media(max-width:600px){body{padding:8px}main{width:374px;max-width:100%;margin:0}.public-profile-page{padding:0}.public-profile-name-row h1{font-size:1.4rem}}</style>
<main id="perfil-preview-stage">${card('bonfire', 'Cineria')}${card('arcane', 'Lyra')}</main>
<div id="fallback-check" style="position:absolute;left:-9999px;width:40px;height:40px" data-cosmetic-layers></div>
<div id="offscreen-check" style="position:absolute;top:3000px;width:40px;height:40px" data-cosmetic-layers>${layer('avatar', 'ember-ring.svg', 'pulse')}</div>
<script src="${url('renderer.js')}"></script><script>
  window.addEventListener('load', () => {
    const broken = document.createElement('img');
    broken.dataset.fallback = '${url('ember-ring.svg')}';
    document.getElementById('fallback-check').appendChild(broken);
    broken.src = '${url('missing.svg')}';
    setTimeout(() => {
    const cards = [...document.querySelectorAll('.public-profile-card')];
    const loaded = [...document.querySelectorAll('.public-profile-card .cosmetic-layer')].every(img => img.complete && img.naturalWidth > 0);
    const actions = [...document.querySelectorAll('.profile-social-btn')];
    const clear = actions.every(button => [...button.closest('.public-profile-card').querySelectorAll('.cosmetic-layers')]
      .every(layer => getComputedStyle(layer).pointerEvents === 'none'));
    const textClear = cards.every(card => [...card.querySelectorAll('.cosmetic-layers--avatar, .cosmetic-layers--ornament')]
      .every(layer => [...card.querySelectorAll('h1, .public-profile-bio, button')].every(text => {
        const a = text.getBoundingClientRect(), b = layer.getBoundingClientRect();
        return a.right <= b.left || a.left >= b.right || a.bottom <= b.top || a.top >= b.bottom;
      })));
    const fallback = document.querySelector('#fallback-check img').naturalWidth > 0;
    const fits = document.documentElement.scrollWidth <= window.innerWidth + 1;
    const bio = document.querySelector('.public-profile-bio');
    const offscreenPaused = !document.querySelector('#offscreen-check .cosmetic-layers').classList.contains('is-visible');
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const motionOk = !reduced || getComputedStyle(document.querySelector('.cosmetic-layer--pulse')).animationName === 'none';
    document.body.dataset.check = JSON.stringify({ cards: cards.length, loaded, clear, textClear, fallback, fits, offscreenPaused, reduced, motionOk, bioWidth: Math.round(bio.getBoundingClientRect().width), cardWidth: Math.round(cards[0].getBoundingClientRect().width) });
    }, 600);
  });
</script></html>`;
const fixture = path.join(temp, 'fixture.html');
fs.writeFileSync(fixture, html, 'utf8');

function run(width, height, label, reduced = false) {
  const screenshot = path.join(screenshotDir, `cosmetic-${label}.png`);
  const result = spawnSync(chrome, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--allow-file-access-from-files', ...(reduced ? ['--force-prefers-reduced-motion=reduce'] : []),
    `--user-data-dir=${path.join(temp, 'chrome-' + label)}`,
    `--window-size=${width},${height}`, '--virtual-time-budget=1800',
    `--screenshot=${screenshot}`, '--dump-dom', pathToFileURL(fixture).href,
  ], { encoding: 'utf8', timeout: 30000, maxBuffer: 3 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr);
  const match = result.stdout.match(/data-check="([^"]+)"/);
  assert.ok(match, 'browser check marker missing');
  const check = JSON.parse(match[1].replaceAll('&quot;', '"'));
  assert.deepEqual({ cards: check.cards, loaded: check.loaded, clear: check.clear, textClear: check.textClear, fallback: check.fallback, fits: check.fits, offscreenPaused: check.offscreenPaused, reduced: check.reduced, motionOk: check.motionOk },
    { cards: 2, loaded: true, clear: true, textClear: true, fallback: true, fits: true, offscreenPaused: true, reduced, motionOk: true });
  assert.ok(check.cardWidth <= width, 'card exceeds screenshot width');
  assert.ok(fs.statSync(screenshot).size > 10000, 'screenshot is empty');
  console.log(`${label}: browser checks OK; screenshot ${screenshot}`);
}

try {
  run(1440, 900, 'desktop');
  run(390, 844, 'mobile');
  run(390, 844, 'reduced', true);
} finally {
  fs.rmSync(temp, { recursive: true, force: true });
}
