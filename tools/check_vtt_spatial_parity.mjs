// Compare the Python port against the actual existing VTT distance module.
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import assert from 'node:assert/strict';

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const vtt = path.resolve(process.argv[2] || path.join(site, '..', 'bonfire-vtt'));
const requireVtt = createRequire(path.join(vtt, 'package.json'));
const {build} = requireVtt('esbuild');
const compiled = await build({absWorkingDir: vtt, entryPoints: ['packages/spatial/src/distance.ts'],
  bundle: true, write: false, format: 'esm', platform: 'node'});
const {distance} = await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`);
const cases = [];
for (const metric of ['manhattan3d','chebyshev3d','euclidean-round','alt-5-10-5']) {
  for (let i=0; i<32; i++) {
    const a = {pos:{x:i%7-3,y:i%5-2,z:i%3-1},sizeCells:{w:1+i%3,h:1+i%2,z:1+i%4}};
    const b = {pos:{x:i%11-5,y:i%13-6,z:i%9-4},sizeCells:{w:1+i%4,h:1+i%3,z:1+i%2}};
    cases.push({metric,a,b});
  }
}
const result = execFileSync('py', ['-3.14','-c',
  'import json,sys; from home.vtt_lab_spatial import distance_units; print(json.dumps([distance_units(v["metric"],v["a"],v["b"]) for v in json.load(sys.stdin)]))'],
  {cwd:site,input:JSON.stringify(cases),encoding:'utf8',windowsHide:true});
const values = JSON.parse(result);
cases.forEach((value,index) => assert.equal(values[index],distance(value.metric,value.a,value.b),JSON.stringify(value)));
console.log(`Spatial parity: ${cases.length} cases match the existing TS engine; no database or pack edits.`);
