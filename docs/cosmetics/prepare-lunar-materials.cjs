/* Delivery conversion only: keep generated RGBA artwork and its alpha unchanged. */
const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require(process.env.BONFIRE_SHARP_MODULE || 'sharp');
const media = path.resolve(__dirname, '../../home/static/cosmetics');
const families = [
  {key:'blood', frameVersion:'v5', disc:'blood-moon-disc-v2', normalized:'blood-moon-disc-v3'},
  {key:'black', frameVersion:'v6', disc:'black-moon-disc-v2', normalized:'black-moon-disc-v3'},
  {key:'crystal', frameVersion:'v6', disc:'crystal-moon-disc-v1', normalized:'crystal-moon-disc-v2'},
];

async function main() {
  for (const family of families) {
    const frame = 'avatar-' + family.key + '-moon-' + family.frameVersion;
    await sharp(path.join(media, frame+'.png')).resize(640,640,{fit:'contain'})
      .webp({quality:90,alphaQuality:100,effort:4}).toFile(path.join(media,frame+'.webp'));
    // Trim transparent padding, not painted content, before giving every disc the same box.
    const source = path.join(media,family.disc+'.png');
    const normalized = await sharp(source).trim({background:'#00000000',threshold:1})
      .resize(640,640,{fit:'contain',background:'#00000000'}).png().toBuffer();
    await fs.writeFile(path.join(media,family.normalized+'.png'),normalized);
    await sharp(normalized).webp({quality:90,alphaQuality:100,effort:4})
      .toFile(path.join(media,family.normalized+'.webp'));
    console.log(frame + ': transparent WebP; '+family.normalized+': normalized 640px');
  }
}
if (require.main === module) main().catch(error=>{console.error(error.message);process.exitCode=1;});
module.exports={families};
