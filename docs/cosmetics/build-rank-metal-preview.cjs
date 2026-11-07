'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'../..');
const r=spawnSync('py',['-3.14','home/js_tests/rank_metal_fixture.py'],{cwd:root,encoding:'utf8',windowsHide:true,timeout:60000});
assert.equal(r.status,0,r.stderr);
const data=JSON.parse(r.stdout);assert.equal(data.cosmetics.length,7);
// File previews cannot fetch CSS masks on every browser; production keeps URLs.
for(const row of data.cosmetics)for(const part of row.closed.avatar){
 if(!part.retract_mask_url)continue;
 const file=path.join(root,'home',part.retract_mask_url.replace(/^\//,''));
 part.retract_mask_url='data:image/webp;base64,'+fs.readFileSync(file).toString('base64');
}
fs.writeFileSync(path.join(__dirname,'rank-metal-preview-data.js'),'window.BonfireRankMetalPreview='+JSON.stringify(data)+';\n');
console.log('Seven validated rank packages ready for offline preview.');
