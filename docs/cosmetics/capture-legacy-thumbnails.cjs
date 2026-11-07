/* One-time authoring captures, not runtime previews on the profile page. */
'use strict';
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const sharp=require(process.env.SHARP_MODULE || 'C:/Users/helio/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const root=path.resolve(__dirname,'../..'),assets=path.join(root,'home/static/cosmetics');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  await page.goto('http://127.0.0.1:8897/docs/cosmetics/20261102-community-catalog.html');
  const picker=page.locator('[data-catalog-type="efeito"]');await picker.locator('[data-catalog-open]').click();
  const registry=JSON.parse(fs.readFileSync(path.join(assets,'catalog-presentation.json')));
  for(const key of ['soft-glow','glass','embers','aurora','starfall']){
   await picker.locator('[data-catalog-key="'+key+'"]').click();
   await page.waitForFunction(k=>document.querySelector('[data-catalog-type="efeito"] [data-catalog-preview] .public-profile-card')?.dataset.profileEffect===k,key);
   await picker.locator('.public-profile-avatar').evaluate(avatar=>{avatar.replaceChildren();avatar.textContent='B';});
   await picker.locator('.cosmetic-preview-identity').evaluate(node=>{node.style.visibility='hidden';});
   await page.waitForTimeout(400);
   const bytes=await picker.locator('[data-catalog-preview] .public-profile-card').screenshot();
   const name='efeito-'+key+'.webp';
   await sharp(bytes).resize(112,112,{fit:'contain',background:{r:0,g:0,b:0,alpha:0}}).webp({quality:85}).toFile(path.join(assets,'thumbs',name));
   registry.items['efeito-'+key]={thumbnail:'cosmetics/thumbs/'+name};
  }
  fs.writeFileSync(path.join(assets,'catalog-presentation.json'),JSON.stringify(registry,null,2)+'\n');
  console.log('Five static legacy-effect thumbnails captured from the real renderer.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
