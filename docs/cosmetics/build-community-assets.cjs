'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const sharp=require(process.env.SHARP_MODULE || 'C:/Users/helio/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const root=path.resolve(__dirname,'../..'),assets=path.join(root,'home/static/cosmetics');
const config=JSON.parse(fs.readFileSync(path.join(__dirname,'community-art-sources.json')));
const sources=process.argv.slice(2).find(arg=>!arg.startsWith('--')) || path.join(process.env.USERPROFILE,'.codex/generated_images',config.generated_session);

async function writePair(source,stem,width,height=width){
 const bytes=await sharp(source).resize(width,height,{fit:'contain',background:{r:0,g:0,b:0,alpha:0}}).ensureAlpha().png().toBuffer();
 await sharp(bytes).png({compressionLevel:9}).toFile(path.join(assets,stem+'.png'));
 await sharp(bytes).webp({lossless:true,effort:6}).toFile(path.join(assets,stem+'.webp'));
 return bytes;
}
async function aperture(bytes){
 const {data,info}=await sharp(bytes).raw().toBuffer({resolveWithObject:true});
 const {width:w,height:h,channels:c}=info,seen=new Uint8Array(w*h),queue=[Math.floor(h/2)*w+Math.floor(w/2)];
 seen[queue[0]]=1;let head=0,minX=w,minY=h,maxX=0,maxY=0;
 while(head<queue.length){
  const i=queue[head++],x=i%w,y=Math.floor(i/w);minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);
  for(const [nx,ny] of [[x-1,y],[x+1,y],[x,y-1],[x,y+1]]){
   const n=ny*w+nx;if(nx<0||nx>=w||ny<0||ny>=h||seen[n]||data[n*c+3]>=32)continue;
   seen[n]=1;queue.push(n);
  }
 }
 assert(queue.length>w*h*.25 && minX>0&&minY>0&&maxX<w-1&&maxY<h-1,'Circular alpha aperture required');
 const cx=(minX+maxX)/2,cy=(minY+maxY)/2;let radius=Math.min(w,h)/2;
 for(let y=0;y<h;y++)for(let x=0;x<w;x++)if(data[(y*w+x)*c+3]>160)radius=Math.min(radius,Math.hypot(x-cx,y-cy));
 return {cx:Number((cx/w*100).toFixed(3)),cy:Number((cy/h*100).toFixed(3)),diameter:Number((radius*2/w*100).toFixed(3))};
}
function manifest(slug,type,layers,extra={}){
 fs.writeFileSync(path.join(assets,slug+'.json'),JSON.stringify({version:1,slug,type,scope:'ambos',...extra,layers},null,2)+'\n');
}
(async()=>{
 fs.mkdirSync(path.join(assets,'thumbs'),{recursive:true});fs.mkdirSync(path.join(assets,'themes'),{recursive:true});
 if(!process.argv.includes('--thumbnails-only')){
 for(const frame of config.frames){
  const stem='community-frame-'+frame.key+'-v1';
  const bytes=await writePair(path.join(sources,frame.file),stem,512);
  const hole=await aperture(bytes);assert(hole.diameter>50&&hole.diameter<90);
  manifest('moldura-'+frame.key,'moldura',[{slot:'avatar',file:stem+'.webp',fallback:stem+'.png',width:512,height:512,motion:'none',aperture:hole}]);
  console.log(JSON.stringify({frame:frame.key,aperture:hole}));
 }
 await writePair(path.join(sources,config.panel.file),'themes/community-forge-panel-v1',1024);
 manifest('tema-guardiao-da-fogueira','tema',[]);
 for(const effect of config.effects){
  const stem='community-effect-'+effect.key+'-v1';await writePair(path.join(sources,effect.file),stem,1200,400);
  const base={slot:'banner',file:stem+'.webp',fallback:stem+'.png',width:1200,height:400,sprite:'full',motion:effect.motion,opacity:.88};
  const layer=effect.motion==='drift' ? {...base,placement:{x:50,y:50,width:112},motion_params:{distance:18,duration:32,delay:-16}} : base;
  manifest('efeito-'+effect.key,'efeito',[layer],{overlay:true});
 }
 }
 const registry={version:1,items:{}};
 for(const filename of fs.readdirSync(assets).filter(n=>/^(moldura|efeito|tema)-[a-z0-9-]+\.json$/.test(n))){
  const pack=JSON.parse(fs.readFileSync(path.join(assets,filename)));const stem=pack.slug;
  const layer=pack.layers?.find(l=>l.slot==='avatar') || pack.layers?.find(l=>l.slot==='banner');
  if(!layer)continue;
  let input=sharp(path.join(assets,layer.fallback));
  if(layer.sprite==='open')input=input.extract({left:0,top:0,width:layer.width/2,height:layer.height});
  if(layer.sprite==='closed')input=input.extract({left:layer.width/2,top:0,width:layer.width/2,height:layer.height});
  // Closed rigs are composed here once; the picker downloads only this thumbnail.
  if(pack.layers.some(l=>l.motion==='retract')){
   const base=await input.resize(160,160).png().toBuffer();const overlays=[];
   for(const plate of pack.layers.filter(l=>l.motion==='retract'))overlays.push({input:await sharp(path.join(assets,plate.fallback)).resize(160,160).png().toBuffer()});
   input=sharp(await sharp(base).composite(overlays).png().toBuffer());
  }
  await input.resize(112,112,{fit:'contain',background:{r:0,g:0,b:0,alpha:0}}).webp({quality:82}).toFile(path.join(assets,'thumbs',stem+'.webp'));
  registry.items[stem]={thumbnail:'cosmetics/thumbs/'+stem+'.webp'};
 }
 const themePanels={
  'lua-vermelha':'blood-panel-v1.webp','lua-negra':'black-panel-v1.webp','lua-cristal':'crystal-panel-v1.webp',
  'vigilia-das-lanternas':'vigilia-panel-v1.webp','guardiao-da-fogueira':'community-forge-panel-v1.webp',
  ...Object.fromEntries(['obsidiana','ametista','topazio','esmeralda','ambar','rubi','diamante'].map(r=>['rank-'+r,'rank-'+r+'-panel-metal-v1.webp']))};
 for(const [key,panel] of Object.entries(themePanels)){
  const stem='tema-'+key;
  await sharp(path.join(assets,'themes',panel)).resize(112,112).webp({quality:82}).toFile(path.join(assets,'thumbs',stem+'.webp'));
  registry.items[stem]={thumbnail:'cosmetics/thumbs/'+stem+'.webp',category:'especial'};
 }
 // Classic thumbnails show palette swatches, not invented illustrated skins.
 const palettes={bonfire:['#db6556','#1a1618'],ember:['#e89c62','#211b18'],arcane:['#ae8bd9','#1d1928'],verdant:['#9cc68d','#19231c'],moonlit:['#adcbdc','#1b2228'],custom:['#be89b9','#1d2024']};
 for(const [key,[accent,surface]] of Object.entries(palettes)){
  const svg='<svg xmlns="http://www.w3.org/2000/svg" width="112" height="112"><rect x="9" y="14" width="94" height="84" rx="4" fill="'+surface+'" stroke="'+accent+'" stroke-width="3"/><rect x="11" y="16" width="90" height="18" fill="'+accent+'"/><circle cx="29" cy="51" r="10" fill="none" stroke="'+accent+'" stroke-width="2"/><path d="M46 48H88M46 56H75M21 75H88M21 83H70" stroke="'+accent+'" stroke-width="3"/></svg>';
  const stem='tema-'+key;await sharp(Buffer.from(svg)).webp({quality:82}).toFile(path.join(assets,'thumbs',stem+'.webp'));
  registry.items[stem]={thumbnail:'cosmetics/thumbs/'+stem+'.webp',category:'classico'};
 }
 const none='<svg xmlns="http://www.w3.org/2000/svg" width="112" height="112"><circle cx="56" cy="56" r="28" fill="none" stroke="#c5c7cc" stroke-width="4"/><path d="M36 36L76 76" stroke="#c5c7cc" stroke-width="4"/></svg>';
 await sharp(Buffer.from(none)).webp({quality:85}).toFile(path.join(assets,'thumbs/none.webp'));
 for(const kind of ['moldura','efeito'])registry.items[kind+'-none']={thumbnail:'cosmetics/thumbs/none.webp'};
 for(const key of ['soft-glow','glass','embers','aurora','starfall']){
  const name='efeito-'+key+'.webp';
  if(fs.existsSync(path.join(assets,'thumbs',name)))registry.items['efeito-'+key]={thumbnail:'cosmetics/thumbs/'+name};
 }
 fs.writeFileSync(path.join(assets,'catalog-presentation.json'),JSON.stringify(registry,null,2)+'\n');
 console.log(JSON.stringify({frames:config.frames.length,effects:config.effects.length,theme:1,thumbnails:Object.keys(registry.items).length}));
})().catch(error=>{console.error(error);process.exitCode=1;});
