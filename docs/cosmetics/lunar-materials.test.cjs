const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require(process.env.BONFIRE_SHARP_MODULE || 'sharp');
const media = path.resolve(__dirname, '../../home/static/cosmetics');
const slugs = ['vermelha','negra','cristal'];

async function main() {
  let reference;
  for (const slug of slugs) {
    const theme = JSON.parse(await fs.readFile(path.join(media,'tema-lua-'+slug+'.json'),'utf8'));
    const disc = theme.layers.find(layer=>layer.file.includes('-disc-'));
    const layout = {width:disc.width,height:disc.height,opacity:disc.opacity,placement:disc.placement,mobile:disc.mobile};
    if (reference) assert.deepEqual(layout,reference,'Moon size, opacity and responsive placement must agree');
    else reference=layout;
    assert.equal(disc.opacity,.85);
    const discMeta = await sharp(path.join(media,disc.file)).metadata();
    assert.equal(discMeta.width,640);
    assert.equal(discMeta.height,640);
    assert.ok(discMeta.hasAlpha);

    const frame = JSON.parse(await fs.readFile(path.join(media,'moldura-lua-'+slug+'.json'),'utf8'));
    const layer = frame.layers[0];
    assert.match(layer.file,/-v4.webp$/);
    assert.deepEqual([layer.aperture.cx,layer.aperture.cy],[50,50]);
    const {data,info} = await sharp(path.join(media,layer.file)).ensureAlpha().raw().toBuffer({resolveWithObject:true});
    assert.equal(info.width,info.height);
    const radius=info.width*layer.aperture.diameter/200;
    let portrait=0,overlap=0,core=0;
    for(let y=0;y<info.height;y++) for(let x=0;x<info.width;x++) {
      const distance=Math.hypot(x+.5-info.width/2,y+.5-info.height/2);
      const alpha=data[(y*info.width+x)*4+3];
      if(distance<radius) {portrait++;if(alpha>128)overlap++;}
      if(distance<info.width*.2 && alpha>16) core++;
    }
    assert.equal(core,0,'Portrait center must stay transparent');
    // Painted ornaments may overlap the contour, never a substantial part of the portrait.
    assert.ok(overlap/portrait<.04,slug+': excessive portrait occlusion');
    console.log(slug+': equal moon layout; clear portrait core; contour overlap '+(100*overlap/portrait).toFixed(2)+'%');
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
