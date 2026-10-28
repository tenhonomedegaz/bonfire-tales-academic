/* Circular geometry is authored here; theme identity stays in the existing moon art. */
const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require(process.env.BONFIRE_SHARP_MODULE || 'sharp');
const media = path.resolve(__dirname, '../../home/static/cosmetics');
const frameVersion = 'v3';
const themes = [
  {key:'blood', moon:'blood-moon-disc-v2.webp', base:'#241418', edge:'#895846', accent:'#d75c55', metal:'#ba8c66'},
  {key:'black', moon:'black-moon-disc-v2.webp', base:'#0c0f10', edge:'#434b49', accent:'#7e9184', metal:'#7a8480'},
  {key:'crystal', moon:'crystal-moon-disc-v1.webp', base:'#26333a', edge:'#92b4c1', accent:'#d3edf5', metal:'#c1d3dc'},
];

function pendant(theme, x, y, size = 1) {
  return `<g transform="translate(${x} ${y}) scale(${size})">
<path d="M-14-13L0-27L14-13L0 1Z" fill="${theme.base}" stroke="${theme.metal}" stroke-width="4"/>
<ellipse cy="12" rx="7" ry="13" stroke="${theme.edge}" stroke-width="6"/>
<ellipse cy="30" rx="7" ry="13" stroke="${theme.metal}" stroke-width="4"/>
<path d="M-23 48A32 32 0 1 0 23 48A24 24 0 0 1-23 48Z" fill="${theme.base}" stroke="${theme.metal}" stroke-width="5" stroke-linejoin="round"/>
<path d="M-22 64Q0 92 22 64" stroke="${theme.accent}" stroke-width="5" stroke-linecap="round"/>
<path d="M0 91L7 101L0 112L-7 101Z" fill="${theme.accent}" stroke="${theme.base}" stroke-width="3"/>
</g>`;
}

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
${pendant(theme, 512, 909, .82)}
${pendant(theme, 211, 816, .9)}
${pendant(theme, 813, 816, .9)}
</g></svg>`;
}

async function main() {
  for (const theme of themes) {
    const moon = await sharp(path.join(media, theme.moon)).resize(160,160,{fit:'cover'}).png().toBuffer();
    const svg = source(theme, moon.toString('base64'));
    const name = 'avatar-' + theme.key + '-moon-' + frameVersion;
    await fs.writeFile(path.join(media,name+'.svg'),svg);
    await sharp(Buffer.from(svg)).resize(1024,1024).png().toFile(path.join(media,name+'.png'));
    await sharp(Buffer.from(svg)).resize(640,640).webp({quality:90,alphaQuality:100,effort:4}).toFile(path.join(media,name+'.webp'));
    console.log(JSON.stringify({name,aperture:{cx:50,cy:50,diameter:70.3125},bytes:(await fs.stat(path.join(media,name+'.webp'))).size}));
  }
}
if (require.main === module) main().catch(error=>{console.error(error.message);process.exitCode=1;});
module.exports={themes,source,frameVersion};
