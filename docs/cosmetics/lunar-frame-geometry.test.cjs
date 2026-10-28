const assert = require('node:assert/strict');
const path = require('node:path');
const sharp = require(process.env.BONFIRE_SHARP_MODULE || 'sharp');
const {themes} = require('./build-lunar-frames.cjs');
const media = path.resolve(__dirname, '../../home/static/cosmetics');

(async () => {
  for (const theme of themes) {
    const image = path.join(media, 'avatar-' + theme.key + '-moon-v2.webp');
    const {data,info} = await sharp(image).ensureAlpha().raw().toBuffer({resolveWithObject:true});
    assert.equal(info.width, info.height);
    const center = info.width / 2;
    const radius = 360 / 1024 * info.width;
    const alpha = (x,y) => data[(y*info.width+x)*4+3];
    for (let y=0;y<info.height;y++) for (let x=0;x<info.width;x++) {
      if (Math.hypot(x+.5-center,y+.5-center) < radius-1.5) {
        assert.equal(alpha(x,y),0,theme.key+': artwork inside portrait circle');
      }
    }
    const boundary=[];
    for(let n=0;n<72;n++) {
      const angle=n/72*Math.PI*2;
      let found=null;
      for(let r=radius-3;r<=radius+5;r+=.25) {
        const x=Math.floor(center+Math.cos(angle)*r),y=Math.floor(center+Math.sin(angle)*r);
        if(alpha(x,y)>128){found=r;break;}
      }
      assert.notEqual(found,null,theme.key+': discontinuous inner ring');
      boundary.push(found);
    }
    assert.ok(Math.max(...boundary)-Math.min(...boundary)<=2,theme.key+': non-circular opening');
    console.log(theme.key+': centered clear circular aperture; radial variation <=2px at640px');
  }
})().catch(error=>{console.error(error.message);process.exitCode=1;});
