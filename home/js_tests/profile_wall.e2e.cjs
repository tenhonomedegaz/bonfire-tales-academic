'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '../..');
const out = process.env.PROFILE_WALL_QA_OUT || path.join(root, 'docs/qa/profile-wall');
const fixture = spawnSync(process.env.BONFIRE_PYTHON || 'py', process.env.BONFIRE_PYTHON ? [path.join(__dirname, 'profile_wall_fixture.py')] : ['-3.14', path.join(__dirname, 'profile_wall_fixture.py')], {encoding: 'utf8'});
assert.equal(fixture.status, 0, fixture.stderr);const html = JSON.parse(fixture.stdout).html;
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (pathname === '/') {res.setHeader('Content-Type', 'text/html; charset=utf-8');return res.end(html);}
  if (pathname.startsWith('/static/')) {
    const file = path.resolve(root, 'home/static', '.' + pathname.slice(7));
    if (file.startsWith(path.join(root, 'home/static')+path.sep) && fs.existsSync(file) && fs.statSync(file).isFile()) {
      res.setHeader('Content-Type', ({'.css':'text/css','.js':'text/javascript','.svg':'image/svg+xml','.webp':'image/webp','.png':'image/png'})[path.extname(file)] || 'application/octet-stream');
      return fs.createReadStream(file).pipe(res);
    }
  }
  res.statusCode = 404;res.end();
});
if (process.argv.includes('--serve')) {
  server.listen(Number(process.argv.at(-1)) || 8898, '127.0.0.1', () => console.log('http://127.0.0.1:'+server.address().port+'/'));
} else (async () => {
  fs.mkdirSync(out,{recursive:true});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser = await chromium.launch({channel:'msedge',headless:true});const report = {widths:[],errors:[]};
  try {
    for (const width of [390,1440]) {
      const page = await browser.newPage({viewport:{width,height:1000},reducedMotion:'reduce'});
      page.on('pageerror',error=>report.errors.push(error.message));
      await page.goto('http://127.0.0.1:'+server.address().port+'/');
      await page.waitForSelector('[data-profile-wall]');
      assert.equal(await page.locator('.profile-character-card .cw-card-portrait').count(),1);
      assert.equal(await page.locator('.profile-character-card .cw-manage').count(),0);
      assert.equal(await page.locator('.profile-character-card a').getAttribute('href'),'/ficha/1/');
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow');
      await page.locator('[data-wall-emojis]').click();await page.locator('[data-wall-emoji="🔥"]').click();
      assert((await page.locator('#wall-text').inputValue()).includes('🔥'));
      await page.locator('#wall-text').fill('**Uma nova aventura**\n\n<script>window.unsafeWall=true</script>\n<img src=x onerror="window.unsafeWall=true">');
      await page.locator('[data-wall-preview]').click();
      assert.equal(await page.locator('#wall-preview strong').textContent(),'Uma nova aventura');
      assert.equal(await page.locator('#wall-preview script,#wall-preview [onerror]').count(),0);
      assert.equal(await page.evaluate(()=>window.unsafeWall),undefined);
      await page.locator('[data-wall-tool="image"]').click();await page.locator('#wall-url').fill('javascript:alert(1)');await page.locator('[data-wall-insert-url]').click();
      assert((await page.locator('[data-wall-editor-status]').textContent()).includes('válido'));
      await page.locator('#wall-url').fill('https://example.com/memoria.png');await page.locator('[data-wall-insert-url]').click();
      assert((await page.locator('#wall-text').inputValue()).includes('](https://example.com/memoria.png)'));
      await page.locator('#wall-text').fill('Que venham as próximas aventuras! 🔥');
      await page.locator('[data-wall-preview]').click();
      await page.route('**/curtir/',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,curtido:true,curtidas:3})}));
      const like=page.locator('[data-wall-like]').first();await like.locator('button').click();
      await page.waitForFunction(()=>document.querySelector('[data-wall-like] button').getAttribute('aria-pressed')==='true');
      assert.equal(await like.locator('[name=curtido]').inputValue(),'false');
      assert.equal(await like.locator('[data-wall-like-count]').textContent(),'3');
      await page.route('**/curtir/',route=>route.fulfill({status:500,body:'error'}));
      await like.locator('button').click();await page.waitForFunction(()=>document.querySelector('[data-wall-like-status]').textContent.includes('Não foi'));
      assert.equal(await like.locator('[data-wall-like-count]').textContent(),'3','No optimistic drift after error');
      await page.locator('[data-wall-like-status]').first().evaluate(e=>e.textContent='');
      await page.locator('[data-wall-emojis]').click();
      await page.screenshot({path:path.join(out,width+'-profile.png'),fullPage:true});
      await page.locator('[data-profile-wall]').screenshot({path:path.join(out,width+'-wall.png')});
      report.widths.push({width,cardReused:true,emoji:true,markdown:true,xssBlocked:true,likeState:true,noOverflow:true});await page.close();
    }
    assert.deepEqual(report.errors,[]);report.passed=true;console.log(JSON.stringify(report));
  } finally {await browser.close();server.close();fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify(report,null,2));}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
