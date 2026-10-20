const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH } : {}) });
  try {
    const origin = process.env.PICKER_ORIGIN;
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    context.setDefaultTimeout(15000);
    await context.route('**/*', r => r.request().url().startsWith(origin) ? r.continue() : r.abort());
    await context.addCookies([{ name: process.env.PICKER_COOKIE_NAME,value:process.env.PICKER_COOKIE_VALUE,url:origin }]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const tools = root => root.locator('xpath=preceding-sibling::*[1]');
    async function snapshot(name) {
      if (!process.env.BONFIRE_ARTIFACT_DIR) return;
      fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR,{recursive:true});
      await page.screenshot({path:path.join(process.env.BONFIRE_ARTIFACT_DIR,name+'.png'),fullPage:true});
    }
    await page.goto(origin+process.env.PICKER_CREATION);
    // Isola a etapa de classe: não afirma aceite do cadastro completo.
    await page.locator('#cf-classe').evaluate(select => {
      document.querySelectorAll('[data-step]').forEach(step => { step.hidden=true; });
      select.closest('[data-step]').hidden=false;
      select.value='arquivista'; select.dispatchEvent(new Event('change',{bubbles:true}));
    });
    const list=page.locator('#cf-magias'), search=tools(list).locator('input[type=search]');
    await search.fill('BENCAO');
    await list.locator('input[value=bencao]').check();
    await search.fill('protection');
    assert.equal(await list.locator('input[value=protecao]').isDisabled(),true,'limite preservado ao filtrar');
    assert.equal(await list.locator('input[value=bencao]').isChecked(),true);
    await tools(list).locator('.spell-picker-summary button').click();
    assert.equal(await list.locator('input[value=bencao]').evaluate(e=>document.activeElement===e),true);
    await search.fill('inexistente');
    assert.match(await tools(list).innerText(),/Nenhum resultado.*1 selecionada/);
    await search.press('Enter');
    assert.equal(new URL(page.url()).pathname,process.env.PICKER_CREATION,'Enter na busca não envia a ficha');
    await search.press('Escape');
    assert.equal(await search.inputValue(),'');
    const prepared=page.locator('#cf-preparadas');
    await prepared.locator('input[value=bencao]').check();
    // Reconstrução conserva busca e reconecta o resumo aos nós novos.
    await list.locator('input[value=bencao]').uncheck();
    await list.locator('input[value=protecao]').check();
    await tools(prepared).locator('input').fill('protecao');
    assert.equal(await prepared.locator('input[value=protecao]').isVisible(),true);
    await snapshot('creation-desktop');
    console.log('criação: busca PT/EN, limite, resumo, vazio, Escape e catálogo dinâmico');

    await page.goto(origin+process.env.PICKER_LEVELUP);
    const step=page.locator('[data-sn-tab]').filter({hasText:'Magias'}).first();
    await step.click();
    const learn=page.locator('[data-lvl-group=magias]');
    const learnSearch=tools(learn).locator('input[type=search]');
    await learnSearch.fill('light');
    await learn.locator('input[value=luz]').check();
    await learnSearch.fill('shield');
    assert.equal(await learn.locator('input[value=luz]').isChecked(),true);
    await snapshot('levelup-desktop');
    console.log('avanço: busca e escolha preservada');

    await page.goto(origin+process.env.PICKER_SHEET);
    await page.setViewportSize({width:360,height:800});
    const sheet=page.locator('.spell-level-grid[data-spell-picker]');
    await tools(sheet).locator('input').fill('protection');
    assert.equal(await sheet.locator('.spell-row:visible').count(),1);
    assert.equal(await sheet.locator('.spell-level-card:visible').count(),1);
    await tools(sheet).locator('.spell-picker-summary button').filter({hasText:'Bênção'}).click();
    assert.equal(await sheet.locator('.spell-row:visible').count(),4);
    assert.equal(await sheet.locator('.spell-row').filter({hasText:'Bênção'}).evaluate(row=>row.contains(document.activeElement)),true,'resumo foca controle visível, não CSRF oculto');
    await tools(sheet).locator('select').selectOption('0');
    assert.equal(await sheet.locator('.spell-row:visible').count(),1);
    await snapshot('preparation-mobile');
    await tools(sheet).locator('select').selectOption('');
    console.log('preparação: busca PT/EN e resumo de preparadas');

    await page.goto(origin+process.env.PICKER_WORKSHOP);
    const shop=page.locator('[data-workshop-list=scrolls]');
    await page.locator('[data-workshop-search=scrolls]').fill('bencao');
    assert.equal(await shop.locator('[data-search]:visible').count(),1);
    await page.locator('[data-workshop-level=scrolls]').selectOption('2');
    assert.equal(await shop.locator('[data-search]:visible').count(),0);
    assert.match(await tools(shop.locator('..')).innerText(),/Nenhum resultado/);
    await page.locator('[data-workshop-level=scrolls]').selectOption('1');
    assert.equal(await shop.locator('[data-search]:visible').count(),1);
    await snapshot('workshop-mobile');
    console.log('oficina: busca acentuada, círculo combinado e vazio');
    // Contrato de selects nativos usado nas trocas e na assinatura, sem alterar dados.
    await page.evaluate(() => {
      const host=document.createElement('div');
      host.innerHTML='<select id="picker-native-test" data-spell-picker="Buscar escolha"><option value="">Selecione</option><option value="a" data-spell-name="Bênção Bless" selected>Bênção</option><option value="b" data-spell-name="Luz Light">Luz</option></select>';
      document.body.append(host);
    });
    const native=page.locator('#picker-native-test');
    await tools(native).locator('input').fill('light');
    assert.equal(await native.inputValue(),'a');
    assert.equal(await native.locator('option[value=a]').evaluate(e=>e.hidden),true);
    await tools(native).locator('.spell-picker-summary button').click();
    assert.equal(await native.evaluate(e=>document.activeElement===e),true);
    assert.equal(await native.inputValue(),'a');
    await native.evaluate(select=>{ select.options[1].disabled=true; select.value=''; });
    await tools(native).locator('.spell-picker-summary button').waitFor({state:'detached'});
    assert.match(await tools(native).innerText(),/0 selecionada/);
    console.log('select nativo: valor preservado e acesso por resumo');
    assert.deepEqual(errors,[]);
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
