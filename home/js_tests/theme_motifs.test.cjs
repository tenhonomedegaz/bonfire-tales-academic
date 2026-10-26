const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const browser = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js/tema_swatch.js'), 'utf8'), browser);
const swatch = browser.window.TemaSwatch;
const motifs = ['none', 'facets', 'runes', 'sun', 'leaves', 'flames', 'thorns', 'crystal', 'moon', 'eclipse', 'bats'];
const attrs = new Map();
const vars = new Map();
const target = { className: 'profile-page effect-glass profile-has-bg theme-bonfire',
  style: { setProperty: (k, v) => vars.set(k, v), removeProperty: k => vars.delete(k) },
  setAttribute: (k, v) => attrs.set(k, v), removeAttribute: k => attrs.delete(k) };
for (const motif of motifs) {
  const card = swatch.leCartao({ closest: () => ({ dataset: { temaCard: 'unrelated-name', motif,
    accent: '#34d399', accent2: '#123456', surface: '#141418', deep: '#09090c' } }) });
  swatch.aplica(target, card);
  assert.equal(attrs.get('data-theme-motif'), motif);
  assert.match(target.className, /effect-glass profile-has-bg/);
  assert.equal(vars.get('--profile-accent-solid'), '#34d399');
}
swatch.aplica(target, { chave: 'anything', accent: '#112233', motif: 'url(evil)' });
assert.equal(attrs.get('data-theme-motif'), 'none');
swatch.aplica(target, { chave: 'custom', accent: '#112233', motif: 'leaves' });
assert.equal(attrs.get('data-theme-motif'), 'none');
swatch.aplica(target, { chave: 'bonfire', classe: 'theme-bonfire' });
assert.equal(attrs.get('data-theme-motif'), 'none');
assert.equal(vars.has('--profile-accent-solid'), false);
console.log('Theme motifs: 11 values, invalid/custom/legacy resets and class preservation OK');
