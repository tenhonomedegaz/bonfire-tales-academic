const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/js/tema_swatch.js'), 'utf8');
const browser = { window: {} };
vm.runInNewContext(source, browser);
const { aplica } = browser.window.TemaSwatch;
const variables = new Map();
const attrs = new Map();
const sheet = {
  className: 'ficha theme-bonfire effect-spark ficha-has-bg',
  style: {
    setProperty: (key, value) => variables.set(key, value),
    removeProperty: key => variables.delete(key),
  },
  setAttribute: (key, value) => attrs.set(key, value),
  removeAttribute: key => attrs.delete(key),
};
const pilot = {
  chave: 'forja-de-brasas', classe: 'theme-data',
  accent: '#ff833b', accent2: '#b31515', surface: '#1b120f', deep: '#0d0908',
  gradiente: true, particula: 'nenhuma', vel: 'lenta',
};
aplica(sheet, pilot);
assert.match(sheet.className, /theme-data collection-forja-de-brasas/);
assert.match(sheet.className, /effect-spark ficha-has-bg/);
assert.equal(variables.get('--sheet-accent-solid'), '#ff833b');

aplica(sheet, { ...pilot, chave: 'aurora-glacial', accent: '#9bdde8' });
assert.match(sheet.className, /collection-aurora-glacial/);
assert.doesNotMatch(sheet.className, /collection-forja-de-brasas/);
aplica(sheet, { chave: 'bonfire', classe: 'theme-bonfire' });
assert.match(sheet.className, /theme-bonfire/);
assert.match(sheet.className, /effect-spark ficha-has-bg/);
assert.doesNotMatch(sheet.className, /collection-|theme-data/);
assert.equal(variables.has('--sheet-accent'), false);
console.log('theme compositions: preview switches and baseline restoration OK');
