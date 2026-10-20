const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.BONFIRE_PLAYWRIGHT_MODULE);
(async()=>{
  const browser=await chromium.launch({headless:true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? {executablePath:process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH} : {})});
  try {
    const origin=process.env.PATHBUILDER_E2E_URL;
    const base=JSON.parse(process.env.PATHBUILDER_E2E_BASE);
    const context=await browser.newContext({viewport:{width:1280,height:900}});
    context.setDefaultTimeout(15000);
    await context.route('**/*',r=>r.request().url().startsWith(origin)?r.continue():r.abort());
    await context.addCookies([{name:process.env.PATHBUILDER_E2E_COOKIE_NAME,value:process.env.PATHBUILDER_E2E_COOKIE_VALUE,url:origin}]);
    await context.addInitScript(base=>{
      if(localStorage.getItem('bonfire:pathbuilder:base')) return;
      const build={modo:'regras',classes:[{slug:'mago',nivel:1,subclasse:''}],atributos_bonus:{},escolhas:{},talentos:[],talentos_raciais:[],itens:[],magias:[]};
      localStorage.setItem('bonfire:pathbuilder:base',JSON.stringify(base));
      localStorage.setItem('bonfire:pathbuilder:base_fp',JSON.stringify(JSON.stringify([base.nome,base.classe,base.raca,base.linhagem,base.essencia,base.antecedente,base.scores])));
      localStorage.setItem('bonfire:pathbuilder:builds',JSON.stringify([build,build]));
    },base);
    const page=await context.newPage();
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    async function previewAfter(action) {
      const waiting=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().includes('/preview'));
      await action();
      const response=await (await waiting).json();
      assert.equal(response.ok,true,JSON.stringify(response.erros));
      await page.waitForFunction(()=>!document.querySelector('#pb-status').textContent.includes('Derivando'));
      return response.build;
    }
    let preview=await previewAfter(()=>page.goto(origin+'/sistemas/pathbuilder/laboratorio/'));
    await page.locator('#pb-folha [data-pb-folha]').waitFor();
    const catalog=await page.locator('#pb-catalogs').textContent().then(JSON.parse);
    async function pickSpell(spell) {
      await page.locator('[data-step-tab="5"]').click();
      await page.locator('#pb-spell-class').selectOption('mago');
      await page.locator('[data-picker="magia"] [data-picker-search]').fill(spell.nome);
      return previewAfter(()=>page.locator(`[data-opt-kind="magia"][data-opt-slug="${spell.slug}"] [data-opt-pick]`).click());
    }
    preview=await pickSpell(catalog.magias.find(m=>m.slug===base.truques[0]));
    await page.locator('[data-step-next]').click();
    assert.equal(await page.locator('[data-step="6"]').isVisible(),true);
    assert.equal(await page.locator('#pb-conclude').isDisabled(),true,'escolhas obrigatórias bloqueiam conclusão');
    console.log(JSON.stringify({classe:'mago',nivel:1,grupos:preview.escolhas_pendentes,erro:preview.validacao.problemas}));
    for(let i=0;i<10&&preview.escolhas_grupos.some(g=>g.pendentes);i++) {
      const group=preview.escolhas_grupos.find(g=>g.pendentes);
      const taken=new Set(group.resolvidas.map(r=>r.valor));
      const option=group.opcoes.find(o=>!o.ja_proficiente&&!taken.has(o.valor));
      assert.ok(option,JSON.stringify(group));
      await page.locator('[data-step-tab="2"]').click();
      preview=await previewAfter(()=>page.locator(`[data-choice-key="${group.key}"][data-choice-val="${option.valor}"] [data-choice-pick]`).click());
    }
    assert.equal(preview.validacao.valida,true,JSON.stringify(preview.validacao));
    await page.locator('[data-step-tab="6"]').click();
    await page.locator('#pb-conclude').click();
    assert.match(await page.locator('#pb-review-status').innerText(),/concluída/);
    // Preparo da base pertence à classe: exceder o teto bloqueia, desfazer recupera.
    await page.locator('[data-step-tab="5"]').click();
    let source=preview.magias_fontes.find(s=>s.slug==='mago');
    const extra=source.magias.find(m=>m.nivel>0&&!m.preparada);
    assert.ok(extra);
    const prep=page.locator(`[data-spell-prepared-slug="${extra.slug}"][data-spell-prepared-class="mago"]`);
    preview=await previewAfter(()=>prep.check());
    assert.ok(preview.validacao.magias.some(p=>p.includes('magias preparadas')));
    assert.equal(preview.magias_fontes[0].conhecidas,source.conhecidas);
    preview=await previewAfter(()=>prep.uncheck());
    assert.equal(preview.validacao.valida,true,JSON.stringify(preview.validacao));
    for(const width of [1280,360]){
      await page.setViewportSize({width,height:900});
      if(process.env.BONFIRE_ARTIFACT_DIR){fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.BONFIRE_ARTIFACT_DIR,'repertoire-'+width+'.png'),fullPage:true});}
    }
    const illegal=catalog.magias.find(m=>m.nivel===9);
    preview=await pickSpell(illegal);
    assert.equal(preview.validacao.valida,false);
    await page.locator('[data-step-next]').click();
    assert.equal(await page.locator('#pb-conclude').isDisabled(),true);
    assert.match(await page.locator('[data-step-tab="5"]').getAttribute('class'),/is-error/);
    assert.match(await page.locator('[data-step-tab="6"]').getAttribute('class'),/is-error/);
    assert.match(await page.locator('#pb-step-err').innerText(),new RegExp(illegal.nome));
    const selected=await page.evaluate(()=>JSON.parse(localStorage.getItem('bonfire:pathbuilder:builds'))[0].magias);
    assert.equal(selected.length,3);
    assert.ok(selected.every(m=>m.classe==='mago'));
    console.log(JSON.stringify({classe:'mago',nivel:1,magias:selected,escolhas:preview.escolhas_grupos.map(g=>({key:g.key,selecionadas:g.selecionadas})),erro:preview.validacao.problemas}));
    for(const width of [1280,360]){
      await page.setViewportSize({width,height:900});
      if(process.env.BONFIRE_ARTIFACT_DIR){fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.BONFIRE_ARTIFACT_DIR,'review-'+width+'.png'),fullPage:true});}
    }
    await page.reload();
    await page.locator('#pb-folha [data-pb-folha]').waitFor();
    assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('bonfire:pathbuilder:builds'))[0].magias),selected);
    await page.locator('[data-step-tab="5"]').click();
    assert.equal(await prep.isChecked(),false);
    assert.deepEqual(errors,[]);
  } finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
