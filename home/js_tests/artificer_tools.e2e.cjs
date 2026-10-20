const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE);
(async () => {
  const browser = await chromium.launch({headless:true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? {executablePath:process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH} : {})});
  try {
    const origin=process.env.TOOLS_ORIGIN;
    const context=await browser.newContext({viewport:{width:1280,height:900}});
    context.setDefaultTimeout(12000);
    await context.route('**/*',r=>r.request().url().startsWith(origin)?r.continue():r.abort());
    await context.addCookies([{name:process.env.TOOLS_COOKIE_NAME,value:process.env.TOOLS_COOKIE_VALUE,url:origin}]);
    const page=await context.newPage();
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(origin+process.env.TOOLS_PATH);
    await page.locator('[data-sn-tab]').filter({hasText:'Opções de classe'}).click();
    const select=page.locator('[data-slug=ferramenta] select');
    const known=select.locator('option').filter({hasText:'Ferreiro'});
    assert.equal(await known.isDisabled(),true);
    assert.match(await known.innerText(),/já proficiente/);
    assert.equal(await page.locator('.lvl-card__hint').filter({hasText:'Ferreiro — já proficiente'}).isVisible(),true);
    assert.equal(await select.locator('option').filter({hasText:'Flauta'}).count(),0);
    for (const width of [1280,360]) {
      await page.setViewportSize({width,height:900});
      await select.focus();
      assert.ok((await select.boundingBox()).height < 80,'seletor compacto em desktop/celular');
      if (process.env.BONFIRE_ARTIFACT_DIR) {
        fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR,{recursive:true});
        await page.screenshot({path:path.join(process.env.BONFIRE_ARTIFACT_DIR,'tools-'+width+'.png'),fullPage:true});
      }
    }
    await select.selectOption({label:'Ferramentas de Carpinteiro'});
    await page.locator('[data-sn-tab]').filter({hasText:'Confirmar'}).click();
    const response=page.waitForResponse(r=>r.request().method()==='POST' && r.url().includes('/aplicar'));
    await page.locator('[data-sn-confirm]').click();
    assert.equal((await response).status(),200);
    await page.waitForTimeout(200);
    await page.goto(origin+process.env.TOOLS_PATH);
    assert.equal(await page.locator('[data-slug=ferramenta] select').count(),0);
    assert.deepEqual(errors,[]);
    console.log('Q08: conhecida desabilitada, categoria correta, escolha e recarga aprovadas');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
