/* Circular geometry is authored here; theme identity stays in the existing moon art. */
const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require(process.env.BONFIRE_SHARP_MODULE || 'sharp');
const media = path.resolve(__dirname, '../../home/static/cosmetics');
const themes = [
  {key:'blood', moon:'blood-moon-disc-v2.webp', base:'#241418', edge:'#895846', accent:'#d75c55', metal:'#ba8c66'},
  {key:'black', moon:'black-moon-disc-v2.webp', base:'#0c0f10', edge:'#434b49', accent:'#7e9184', metal:'#7a8480'},
  {key:'crystal', moon:'crystal-moon-disc-v1.webp', base:'#26333a', edge:'#92b4c1', accent:'#d3edf5', metal:'#c1d3dc'},
];

function source(theme, moon) {
  return `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1024 1024" width="1024" height="1024" fill="none">
<defs><clipPath id="moon"><circle cx="512" cy="82" r="60"/></clipPath><mask id="portrait"><rect width="1024" height="1024" fill="white"/><circle cx="512" cy="512" r="360" fill="black"/></mask></defs>
<g mask="url(#portrait)">
<circle cx="512" cy="512" r="382" stroke="${theme.base}" stroke-width="44"/>
<circle cx="512" cy="512" r="402" stroke="${theme.edge}" stroke-width="5"/>
<circle cx="512" cy="512" r="363" stroke="${theme.metal}" stroke-width="6"/>
<circle cx="512" cy="512" r="386" stroke="${theme.accent}" stroke-width="9" stroke-dasharray="270 943 270 943" stroke-dashoffset="-134"/>
<circle cx="512" cy="512" r="413" stroke="${theme.metal}" stroke-width="2" stroke-opacity=".55" stroke-dasharray="84 565 84 565 84 1213"/>
<path d="M495 117L512 134L529 117M495 901L512 884L529 901" stroke="${theme.metal}" stroke-width="5" stroke-linejoin="round"/>
<circle cx="512" cy="82" r="66" fill="${theme.base}" stroke="${theme.edge}" stroke-width="5"/>
<image x="452" y="22" width="120" height="120" preserveAspectRatio="xMidYMid slice" clip-path="url(#moon)" xlink:href="data:image/png;base64,${moon}"/>
<circle cx="512" cy="82" r="61" stroke="${theme.metal}" stroke-width="3"/>
<path d="M106 493a20 20 0 1 0 0 38a22 22 0 0 1 0-38ZM918 493a20 20 0 1 1 0 38a22 22 0 0 0 0-38Z" fill="${theme.accent}" stroke="${theme.base}" stroke-width="4"/>
<circle cx="512" cy="918" r="13" fill="${theme.base}" stroke="${theme.metal}" stroke-width="3"/>
<path d="M512 905a13 13 0 0 1 0 26Z" fill="${theme.accent}"/>
</g></svg>`;
}

async function main() {
  for (const theme of themes) {
    const moon = await sharp(path.join(media, theme.moon)).resize(160,160,{fit:'cover'}).png().toBuffer();
    const svg = source(theme, moon.toString('base64'));
    const name = 'avatar-' + theme.key + '-moon-v2';
    await fs.writeFile(path.join(media,name+'.svg'),svg);
    await sharp(Buffer.from(svg)).resize(1024,1024).png().toFile(path.join(media,name+'.png'));
    await sharp(Buffer.from(svg)).resize(640,640).webp({quality:90,alphaQuality:100,effort:4}).toFile(path.join(media,name+'.webp'));
    console.log(JSON.stringify({name,aperture:{cx:50,cy:50,diameter:70.3125},bytes:(await fs.stat(path.join(media,name+'.webp'))).size}));
  }
}
if (require.main === module) main().catch(error=>{console.error(error.message);process.exitCode=1;});
module.exports={themes,source};
