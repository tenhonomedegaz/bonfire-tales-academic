const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require(process.env.BONFIRE_SHARP_MODULE || 'sharp');
const {createHash} = require('node:crypto');
const media = path.resolve(__dirname, '../../home/static/cosmetics');
const slugs = ['vermelha','negra','cristal'];
const originalHashes = {
  vermelha:'a028c576b1e9273c2144fca730c650b8ef2747610d6bb881c3f8cc8dbdb41e98',
  negra:'8337e468211845f1e8ddef25c47122d0917f2203de9fbb8a1365f9a0262dee19',
  cristal:'89671376c0ddc03463816bd0a3c682297f5933df20b3b5bebf03678e078b78b9',
};

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
    assert.match(layer.file,slug === 'vermelha' ? /-v5.webp$/ : /-v6.webp$/);
    const master = await fs.readFile(path.join(media,layer.fallback));
    assert.equal(createHash('sha256').update(master).digest('hex'),originalHashes[slug],
      'Keep the original artwork; portrait calibration must not redraw the frame');
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
    // Original inward pendants are intentional; do not cut them away to fit a synthetic hole.
    console.log(slug+': unchanged original master; equal moon layout; clear portrait core; decorative overlap '+(100*overlap/portrait).toFixed(2)+'%');
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
