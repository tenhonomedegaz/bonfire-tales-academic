/** Rebuild the visual bridge only, never the VTT rules, host or content packs. */
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs/promises';
import { createHash } from 'node:crypto';

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const vtt = path.resolve(process.argv[2] || path.join(site, '..', 'bonfire-vtt'));
const requireVtt = createRequire(path.join(vtt, 'package.json'));
const { build } = requireVtt('esbuild');
const out = path.join(site, 'home/static/vtt');
await fs.mkdir(out, { recursive: true });
const result = await build({absWorkingDir: vtt,
  entryPoints: ['apps/client/src/siteLabRenderer.ts'], bundle: true, minify: true,
  format: 'esm', platform: 'browser', target: 'es2022', legalComments: 'external',
  outfile: path.join(out, 'renderer.js'), metafile: true});
const inputs = [];
for (const input of Object.keys(result.metafile.inputs).sort()) {
  const normalized = input.replaceAll('\\', '/');
  if (normalized.includes('/core/') || normalized.includes('/net/') || normalized.includes('ref/')) {
    throw new Error(`Unexpected rules, network or reference input: ${input}`);
  }
  inputs.push({file: normalized, sha256: createHash('sha256').update(await fs.readFile(path.resolve(vtt, input))).digest('hex')});
}
const bytes = await fs.readFile(path.join(out, 'renderer.js'));
await fs.writeFile(path.join(out, 'renderer.manifest.json'), JSON.stringify({
  schema: 1, entry: 'apps/client/src/siteLabRenderer.ts',
  sha256: createHash('sha256').update(bytes).digest('hex'), bytes: bytes.length,
  authority: 'django-python', inputs,
}, null, 2) + '\n');
await fs.copyFile(requireVtt.resolve('three').replace(/build[\\/]three\.cjs$/, 'LICENSE'), path.join(out, 'THREE-LICENSE.txt'));
console.log(`Visual bridge: ${bytes.length} bytes, ${inputs.length} pinned inputs. No TS rules/host bundled.`);
