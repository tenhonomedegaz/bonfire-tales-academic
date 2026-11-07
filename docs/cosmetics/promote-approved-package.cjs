// Copy approved presentation data and verify every referenced local asset.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),assetRoot=path.join(root,'home/static/cosmetics');
const [source]=process.argv.slice(2);assert(source,'Usage: node promote-approved-package.cjs SOURCE_JSON');
const input=path.resolve(root,source);assert(input.startsWith(root+path.sep));
const pack=JSON.parse(fs.readFileSync(input,'utf8'));assert.equal(pack.version,1);
assert(/^(tema|moldura|efeito)-[a-z0-9-]+$/.test(pack.slug));assert(pack.layers.length<=8);
const assets=new Set();
function check(layer){
  for(const name of [layer.file,layer.fallback,layer.mask?.file].filter(Boolean)) {
    assert(/^[a-z0-9-]+\.(webp|png|svg|gif)$/.test(name));
    assert(fs.statSync(path.join(assetRoot,name)).size<=4*1024*1024,name);assets.add(name);
  }
  (layer.parts||[]).forEach(check);
}
pack.layers.forEach(check);
const body=JSON.stringify(pack)+'\n';assert(Buffer.byteLength(body)<=64*1024);
const target=path.join(assetRoot,pack.slug+'.json');fs.writeFileSync(target,body);
console.log(JSON.stringify({target:path.relative(root,target).replaceAll('\\','/'),bytes:Buffer.byteLength(body),assets:[...assets].sort()}));
