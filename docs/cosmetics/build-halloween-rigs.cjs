/* Retained command name: inspect the approved rig, never rebuild rejected drafts. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '../../home/static/cosmetics');
const pack = JSON.parse(fs.readFileSync(path.join(root, 'efeito-vigilia-das-lanternas.json'), 'utf8'));
assert.equal(pack.version, 1);
assert.equal(pack.slug, 'efeito-vigilia-das-lanternas');
const fire = pack.layers.findIndex(layer => layer.file === 'vigilia-jack-fire-textured-v32.webp');
const face = pack.layers.findIndex(layer => layer.file === 'cosmetic-empty.svg' && layer.parts?.length === 6);
assert(fire >= 0 && face > fire, 'Approved fire must remain behind the face');
assert.equal(pack.layers[face].sequence.duration, 16);
function inspect(layer) {
  for (const file of [layer.file, layer.fallback, layer.mask?.file].filter(Boolean)) {
    assert(!file.includes('/') && !file.includes('\\'), 'Flat asset path required');
    assert(fs.existsSync(path.join(root, file)), 'Missing asset: ' + file);
  }
  for (const part of layer.parts || []) inspect(part);
}
pack.layers.forEach(inspect);
if (process.argv.includes('--export-preview')) {
  const result = spawnSync(process.execPath, [path.join(__dirname, 'build-halloween-preview.cjs')], {stdio:'inherit'});
  if (result.status !== 0) process.exit(result.status || 1);
}
console.log(JSON.stringify({approved:true,manifestUntouched:true,rootLayers:pack.layers.length,
  faceParts:pack.layers[face].parts.length,cycleSeconds:16,fireBehindFace:true,
  previewExported:process.argv.includes('--export-preview')}));
