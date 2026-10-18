/* Bonfire spell deck. Code-built cards with user-supplied school icons. */
(function(){
  'use strict';
  var pageRoot=document.querySelector('.spell-page');
  if(!pageRoot) return;
  var MAGIAS, CLASSES, SCHOOLS, DISPLAY;
  try {
    MAGIAS=JSON.parse(document.getElementById('mg-data').textContent||'[]');
    CLASSES=JSON.parse(document.getElementById('mg-classes').textContent||'[]');
    SCHOOLS=JSON.parse(document.getElementById('mg-schools').textContent||'[]');
    DISPLAY=JSON.parse(document.getElementById('mg-display').textContent||'{}');
  } catch(_) { return; }
  if(!Array.isArray(MAGIAS)||!Array.isArray(CLASSES)||!Array.isArray(SCHOOLS)) return;
  SCHOOLS=SCHOOLS.map(function(school){
    return typeof school==='string'?{key:norm(school).trim(),label:school}:school;
  });
  DISPLAY=Object.assign(Object.create(null),DISPLAY);
  var guideTemplate=document.getElementById('mgGuideTemplate');
  var listContainer=document.getElementById('mgList');
  var resultsContainer=document.getElementById('mgResults');
  var detailContainer=document.getElementById('mgDetail');
  var mount=document.getElementById('mgCardMount');
  var count=document.getElementById('mg-count');
  var fBusca=document.getElementById('mg-busca'), fClasse=document.getElementById('mg-classe'), fEscola=document.getElementById('mg-escola'),
      fNivel=document.getElementById('mg-nivel'), fConc=document.getElementById('mg-conc'), fRitual=document.getElementById('mg-ritual');
  var activeFilters=document.getElementById('mg-active-filters');
  var clearFilters=document.getElementById('mg-clear-filters');
  var mobileMenuButton=document.getElementById('mgMobileMenuButton');
  var mobileBackdrop=document.getElementById('mgMobileBackdrop');
  var mobileClose=document.getElementById('mgCloseFilters');
  var mobileApply=document.getElementById('mgApplyMobile');
  var mobileLayout=window.matchMedia('(max-width: 1100px)');
  var backToDeck=document.getElementById('mgBackToDeck');
  var previousSpell=document.getElementById('mgPreviousSpell'), nextSpell=document.getElementById('mgNextSpell');
  var deckTitle=document.getElementById('mgDeckTitle');
  var notice=document.getElementById('mgLinkNotice');
  var selectedSlug=null, filtered=MAGIAS.slice();
  var menuOpen=false, outsideInert=new Map();
  function norm(s){return (s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();}
  function esc(v){var d=document.createElement('div'); d.textContent=v==null?'':String(v); return d.innerHTML;}
  function attr(v){return esc(v).replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
  function md(v){
    if(!v) return '<p class="text-[var(--muted)]">Sem descrição.</p>';
    if(typeof renderBonfireMarkdown==='function') return sanitizeBonfireMarkdownHtml(renderBonfireMarkdown(v));
    if(window.marked&&window.marked.parse) return sanitizeBonfireMarkdownHtml(window.marked.parse(v,{gfm:true,breaks:true}));
    return esc(v).replace(/\n/g,'<br>');
  }
  function meta(label,val){return val?'<div class="min-w-0"><dt class="text-xs text-[var(--muted)]">'+label+'</dt><dd class="break-words font-medium text-[var(--text)]">'+esc(val)+'</dd></div>':'';}
  function cookie(name){var row=document.cookie.split('; ').find(function(v){return v.indexOf(name+'=')===0;});return row?decodeURIComponent(row.split('=').slice(1).join('=')):'';}
  function editor(m){
    if(!CAN_EDIT) return '';
    var levels=''; for(var n=0;n<=9;n++) levels+='<option value="'+n+'"'+(Number(m.nivel)===n?' selected':'')+'>'+(n===0?'Truque':n+'º círculo')+'</option>';
    var classes=CLASSES.map(function(c){return '<option value="'+attr(c.slug)+'"'+((m.classes_slugs||[]).indexOf(c.slug)>=0?' selected':'')+'>'+esc(c.nome)+'</option>';}).join('');
    function input(label,name,value,wide){return '<label class="flex flex-col gap-1 text-[11px] text-[var(--muted)] '+(wide?'sm:col-span-2':'')+'">'+label+'<input class="rounded border border-[var(--stroke)] bg-[var(--bg0)] px-2 py-1.5 text-[var(--text)]" name="'+name+'" value="'+attr(value||'')+'"></label>';}
    return '<details class="mt-5 border-t border-[var(--stroke)] pt-3" data-spell-editor-container><summary class="cursor-pointer text-xs font-bold uppercase text-[var(--ember)]">Editar magia</summary>'
      +'<form class="mt-3 grid gap-2 sm:grid-cols-2" data-spell-editor data-url="'+attr(m.update_url)+'">'
      +input('Nome','nome',m.nome)+input('Nome em inglês','nome_ingles',m.nome_ingles)
      +input('Slug','slug',m.slug)+input('Escola','escola',m.escola)
      +'<label class="flex flex-col gap-1 text-[11px] text-[var(--muted)]">Círculo<select name="nivel" class="rounded border border-[var(--stroke)] bg-[var(--bg0)] px-2 py-1.5 text-[var(--text)]">'+levels+'</select></label>'
      +input('Tempo de conjuração','casting_time',m.casting_time)+input('Alcance','alcance',m.alcance)+input('Duração','duracao',m.duracao)
      +input('Componentes','componentes',m.componentes,true)
      +'<label class="flex items-center gap-2 text-xs text-[var(--muted)]"><input type="checkbox" name="concentracao"'+(m.concentracao?' checked':'')+'> Concentração</label>'
      +'<label class="flex items-center gap-2 text-xs text-[var(--muted)]"><input type="checkbox" name="ritual"'+(m.ritual?' checked':'')+'> Ritual</label>'
      +'<label class="flex flex-col gap-1 text-[11px] text-[var(--muted)] sm:col-span-2">Classes com acesso base<select name="classes_slugs" multiple size="8" class="rounded border border-[var(--stroke)] bg-[var(--bg0)] px-2 py-1.5 text-[var(--text)]">'+classes+'</select></label>'
      +'<label class="flex flex-col gap-1 text-[11px] text-[var(--muted)] sm:col-span-2">Descrição<textarea name="descricao" rows="10" class="rounded border border-[var(--stroke)] bg-[var(--bg0)] p-2 text-[var(--text)]">'+esc(m.descricao||'')+'</textarea></label>'
      +'<label class="flex flex-col gap-1 text-[11px] text-[var(--muted)] sm:col-span-2">Em níveis superiores<textarea name="em_niveis_superiores" rows="5" class="rounded border border-[var(--stroke)] bg-[var(--bg0)] p-2 text-[var(--text)]">'+esc(m.em_niveis||'')+'</textarea></label>'
      +'<label class="flex flex-col gap-1 text-[11px] text-[var(--muted)] sm:col-span-2">Tags, uma por linha<textarea name="tags_json" rows="9" class="rounded border border-[var(--stroke)] bg-[var(--bg0)] p-2 font-mono text-[11px] text-[var(--text)]">'+esc((m.tags||[]).join('\n'))+'</textarea></label>'
      +'<div class="flex items-center gap-3 sm:col-span-2"><button type="button" data-editor-cancel class="rounded border border-[var(--stroke)] px-3 py-2 text-xs font-bold text-[var(--muted)]">Cancelar</button><button type="submit" class="rounded border border-[var(--ember)] px-3 py-2 text-xs font-bold text-[var(--ember)]">Salvar magia</button><span data-editor-status role="status" tabindex="-1" class="text-xs text-[var(--muted)]"></span></div>'
      +'</form></details>';
  }

  function filtra(){
    var q=norm(fBusca.value.trim()), classe=fClasse.value, esc_=fEscola.value, nv=fNivel.value, conc=fConc.checked, rit=fRitual.checked;
    return MAGIAS.filter(function(m){
      if(classe && (m.classes_lista||[]).indexOf(classe)===-1) return false;
      if(esc_ && m.escola!==esc_) return false;
      if(nv!=='' && String(m.nivel)!==nv) return false;
      if(conc && !m.concentracao) return false;
      if(rit && !m.ritual) return false;
      if(q && norm(m.nome+' '+(m.nome_ingles||'')+' '+m.descricao+' '+(m.tags||[]).join(' ')).indexOf(q)===-1) return false;
      return true;
    });
  }


  function schoolInfo(value) {
    var key=norm(value).trim();
    return SCHOOLS.find(function(school){return school.key===key;}) || {key:'arcana',label:value||'Escola não informada'};
  }
  function symbol(school) {
    if(school.icon_url) return '<img class="spell-school-icon" src="'+attr(school.icon_url)+'" width="40" height="40" alt="" aria-hidden="true" decoding="async">';
    return '<svg viewBox="0 0 40 40" aria-hidden="true" focusable="false"><use href="#spell-school-'+attr(school.key)+'"></use></svg>';
  }
  function levelTile(m) {
    return '<div class="spell-circle"><span>'+esc(m.nivel)+'</span><small>'+(Number(m.nivel)===0?'Truque':'Círculo')+'</small></div>';
  }
  function traits(m, full) {
    return '<div class="spell-traits">'+(full?'<span>'+esc(m.nivel_label)+'</span>':'')
      +(m.concentracao?'<span>Concentração</span>':'')+(m.ritual?'<span>Ritual</span>':'')+'</div>';
  }
  function footer(m, school, full) {
    return '<footer class="spell-card-footer"><span>Bonfire Tales <small>RPG</small></span><span>'+esc(full?school.label:m.nivel_label)+'</span></footer>';
  }
  function formatCopy(container) {
    // Preserve all words; change only visual grouping and heading depth.
    container.querySelectorAll('table').forEach(function(table){
      var header=table.tHead&&table.tHead.rows[0];
      if(!header||header.cells.length<4) return;
      var labels=Array.from(header.cells).map(function(cell){cell.scope='col';return cell.textContent;});
      table.dataset.stackedOnMobile='true';
      Array.from(table.tBodies).forEach(function(body){
        Array.from(body.rows).forEach(function(row){
          Array.from(row.cells).forEach(function(cell,index){cell.dataset.columnLabel=labels[index]||'Detalhe';});
        });
      });
    });
    container.querySelectorAll('h1,h2').forEach(function(heading){
      var replacement=document.createElement('h3');
      while(heading.firstChild) replacement.appendChild(heading.firstChild);
      heading.replaceWith(replacement);
    });
    container.querySelectorAll('p > strong:first-child, li > strong:first-child').forEach(function(label){
      if(/[:.]\s*$/.test(label.textContent)&&label.textContent.length<=70) label.classList.add('spell-rule-label');
    });
  }
  function fullCard(m) {
    var school=schoolInfo(m.escola);
    var facts=DISPLAY[m.slug]||{range:m.alcance,area:'Consulte o efeito da magia'};
    function field(label,value,extra) {return '<div'+(extra?' class="'+extra+'"':'')+'><dt>'+label+'</dt><dd>'+esc(value)+'</dd></div>';}
    mount.innerHTML='<article class="spell-card spell-card-full" data-school="'+attr(school.key)+'" data-full-spell="'+attr(m.slug)+'">'
      +'<header class="spell-card-header"><div class="spell-card-school">'+symbol(school)+'<span>'+esc(school.label)+'</span></div>'+levelTile(m)
      +'<h2 id="magia-'+attr(m.slug)+'" tabindex="-1">'+esc(m.nome)+'</h2>'+(m.nome_ingles?'<p class="spell-english">'+esc(m.nome_ingles)+'</p>':'')+traits(m,true)+'</header>'
      +'<div class="spell-card-body"><dl class="spell-meta">'
      +field('Tempo de conjuração',facts.casting_time||m.casting_time||'Não informado')+field('Alcance',facts.range||'Não informado')
      +field('Duração',facts.duracao||m.duracao||'Não informada')+field('Área de efeito',facts.area||'Consulte o efeito da magia','spell-meta-area')
      +field('Concentração / Ritual',(m.concentracao?'Sim':'Não')+' / '+(m.ritual?'Sim':'Não'))
      +field('Componentes',facts.componentes||m.componentes||'Não informado','spell-meta-components')+'</dl>'
      +(m.classes?'<p class="spell-classes"><span>Classes</span>'+esc(m.classes)+'</p>':'')
      +'<section class="spell-effect" aria-labelledby="mg-description-title"><h3 id="mg-description-title">Efeito da magia</h3><div class="spell-copy bonfire-markdown" data-spell-description>'+md(facts.descricao===undefined?m.descricao:facts.descricao)+'</div></section>'
      +(m.em_niveis?'<section class="spell-upcast"><h3>Em níveis superiores</h3><div class="spell-copy bonfire-markdown" data-spell-upcast>'+md(facts.em_niveis===undefined?m.em_niveis:facts.em_niveis)+'</div></section>':'')
      +(CAN_EDIT&&(m.tags||[]).length?'<details class="spell-technical"><summary>Tags do editor</summary>'+(m.tags||[]).map(function(tag){return '<code>'+esc(tag)+'</code>';}).join('')+'</details>':'')
      +editor(m)+'</div>'+footer(m,school,true)+'</article>';
    mount.querySelectorAll('.spell-copy').forEach(formatCopy);
    bindEditor();
  }
  function bindEditor(){
    var editForm=detailContainer.querySelector('[data-spell-editor]');
    if(editForm){
      var editorDetails=editForm.closest('[data-spell-editor-container]');
      var editorSummary=editorDetails.querySelector('summary');
      var editorStatus=editForm.querySelector('[data-editor-status]');
      var editorControls=Array.from(editForm.querySelectorAll('input, select, textarea, button'));
      function closeSpellEditor(){
        if(editForm.getAttribute('aria-busy')==='true') return;
        editForm.reset();
        editorStatus.textContent='';
        editorDetails.open=false;
        editorSummary.focus();
      }
      editorDetails.addEventListener('click',function(event){
        if(event.target.closest('summary') && editForm.getAttribute('aria-busy')==='true') event.preventDefault();
      });
      editorDetails.addEventListener('keydown',function(event){
        if(event.key==='Escape' && editForm.getAttribute('aria-busy')!=='true'){
          event.preventDefault();
          closeSpellEditor();
        }
      });
      editForm.querySelector('[data-editor-cancel]').addEventListener('click',closeSpellEditor);
      editForm.addEventListener('submit',function(event){
        event.preventDefault();
        if(editForm.getAttribute('aria-busy')==='true') return;
        var fd=new FormData(editForm);
        var payload={};
        ['nome','nome_ingles','slug','escola','casting_time','alcance','componentes','duracao','descricao','em_niveis_superiores'].forEach(function(key){payload[key]=fd.get(key)||'';});
        payload.nivel=Number(fd.get('nivel')||0); payload.concentracao=fd.has('concentracao'); payload.ritual=fd.has('ritual');
        payload.classes_slugs=Array.from(editForm.querySelector('[name="classes_slugs"]').selectedOptions).map(function(o){return o.value;});
        payload.tags_json=(fd.get('tags_json')||'').split(/\r?\n/).map(function(v){return v.trim();}).filter(Boolean);
        editorStatus.setAttribute('role','status');
        editorStatus.textContent='Salvando...';
        editForm.setAttribute('aria-busy','true');
        editorControls.forEach(function(control){control.disabled=true;});
        fetch(editForm.dataset.url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':cookie('csrftoken')},body:JSON.stringify(payload)})
          .then(function(response){return response.json().then(function(data){if(!response.ok)throw new Error(data.error||'Não foi possível salvar.');return data;});})
          .then(function(data){location.href=location.pathname+'?magia='+encodeURIComponent(data.spell.slug)+'&editado=1';})
          .catch(function(error){editorStatus.setAttribute('role','alert');editorStatus.textContent=error.message||'Não foi possível salvar.';editorStatus.focus();})
          .finally(function(){editForm.removeAttribute('aria-busy');editorControls.forEach(function(control){control.disabled=false;});});
      });
    }


  }
  function renderList(){
    var scroll=resultsContainer.scrollTop, focused=document.activeElement;
    var focusedSlug=resultsContainer.contains(focused)?focused.dataset.slug:null;
    var fragment=document.createDocumentFragment();
    filtered.forEach(function(m){
      var link=document.createElement('a'), school=schoolInfo(m.escola), target=consultationUrl(m.slug);
      link.href=target.pathname+target.search;
      link.dataset.slug=m.slug; link.dataset.school=school.key;
      if(selectedSlug===m.slug) link.setAttribute('aria-current','true');
      link.innerHTML='<span class="spell-name-marker" aria-hidden="true"></span><span class="spell-name-copy">'+esc(m.nome)+'</span><small title="'+attr(m.nivel_label)+'">'+esc(m.nivel)+'</small>';
      fragment.appendChild(link);
    });
    resultsContainer.replaceChildren();
    if(!filtered.length){
      resultsContainer.innerHTML='<p class="spell-list-empty">'+(MAGIAS.length?'Nenhuma magia encontrada. Tente outro termo ou limpe os filtros.':'Nenhuma magia cadastrada no momento.')+'</p>';
    } else resultsContainer.appendChild(fragment);
    resultsContainer.scrollTop=scroll;
    if(focusedSlug){
      var replacement=Array.from(resultsContainer.querySelectorAll('[data-slug]')).find(function(link){return link.dataset.slug===focusedSlug;});
      if(replacement) replacement.focus({preventScroll:true});
    }
  }
  function render(){
    filtered=filtra();
    count.textContent=filtered.length;
    document.getElementById('mg-count-label').textContent=filtered.length===1?'magia':'magias';
    document.getElementById('mgSidebarCount').textContent=filtered.length;
    document.getElementById('mgDrawerCount').textContent=filtered.length;
    var active=[];
    if(fBusca.value.trim()) active.push('Busca: '+fBusca.value.trim());
    if(fClasse.value) active.push(fClasse.value);
    if(fEscola.value) active.push(fEscola.value);
    if(fNivel.value!=='') active.push(fNivel.options[fNivel.selectedIndex].text);
    if(fConc.checked) active.push('Concentração');
    if(fRitual.checked) active.push('Ritual');
    activeFilters.textContent=active.join(' · ');
    activeFilters.hidden=clearFilters.hidden=!active.length;
    document.getElementById('mgMobileFilterCount').textContent=active.length;
    document.getElementById('mgMobileFilterCount').hidden=!active.length;
    var filterCount=active.length-(fBusca.value.trim()?1:0);
    document.getElementById('mgFilterCount').textContent=filterCount;
    document.getElementById('mgFilterCount').hidden=!filterCount;
    document.querySelectorAll('[data-school-filter]').forEach(function(button){button.setAttribute('aria-pressed',String(button.dataset.schoolFilter===fEscola.value));});
    var selected=filtered.find(function(m){return m.slug===selectedSlug;});
    if(selectedSlug&&!selected) selectedSlug=null;
    deckTitle.textContent=selected?'Carta selecionada':'Carta-guia';
    renderList();
    if(selected){
      fullCard(selected);
      var position=filtered.indexOf(selected);
      previousSpell.disabled=position<=0; nextSpell.disabled=position>=filtered.length-1;
    } else {
      mount.replaceChildren(guideTemplate.content.cloneNode(true));
      previousSpell.disabled=nextSpell.disabled=true;
    }
  }
  function readFiltersFromUrl(){
    var params=new URLSearchParams(location.search);
    fBusca.value=params.get('busca')||'';
    [[fClasse,'classe'],[fEscola,'escola'],[fNivel,'nivel']].forEach(function(pair){
      var value=params.get(pair[1])||'';
      pair[0].value=Array.from(pair[0].options).some(function(option){return option.value===value;})?value:'';
    });
    fConc.checked=params.get('concentracao')==='1'; fRitual.checked=params.get('ritual')==='1';
  }
  function consultationUrl(slug){
    var url=new URL(location.href);
    [['busca',fBusca.value.trim()],['classe',fClasse.value],['escola',fEscola.value],['nivel',fNivel.value],
     ['concentracao',fConc.checked?'1':''],['ritual',fRitual.checked?'1':'']].forEach(function(pair){
      if(pair[1]) url.searchParams.set(pair[0],pair[1]); else url.searchParams.delete(pair[0]);
    });
    if(slug) url.searchParams.set('magia',slug); else url.searchParams.delete('magia');
    url.searchParams.delete('editado'); url.searchParams.delete('pagina'); url.hash='';
    return url;
  }
  function syncFiltersToUrl(replace){
    var url=consultationUrl(selectedSlug);
    history[replace?'replaceState':'pushState'](null,'',url);
  }
  function applyFilters(replace){
    resultsContainer.scrollTop=0; notice.hidden=true;
    render(); syncFiltersToUrl(replace);
  }
  function selectMagia(slug){
    if(!filtered.some(function(m){return m.slug===slug;})) return;
    var wasMobile=mobileLayout.matches;
    selectedSlug=slug; notice.hidden=true;
    render(); syncFiltersToUrl(false); closeMenu(false);
    var heading=mount.querySelector('h2');
    if(wasMobile) heading.focus({preventScroll:true});
    if(wasMobile||deckTitle.getBoundingClientRect().top<85) deckTitle.scrollIntoView({block:'start'});
  }
  function selectFromUrl(){
    readFiltersFromUrl();
    var requested=new URLSearchParams(location.search).get('magia');
    if(!requested&&location.hash.startsWith('#magia-')){
      try {requested=decodeURIComponent(location.hash.slice(7));} catch(_) {}
    }
    var exists=requested&&MAGIAS.some(function(m){return m.slug===requested;});
    selectedSlug=exists?requested:null;
    render();
    if(exists&&selectedSlug!==requested) syncFiltersToUrl(true);
    notice.hidden=!requested||Boolean(exists);
    notice.textContent='A magia deste link não foi encontrada. Escolha um nome na lista.';
    if(selectedSlug&&mobileLayout.matches){
      var heading=mount.querySelector('h2');
      if(heading){heading.focus({preventScroll:true});deckTitle.scrollIntoView({block:'start'});}
    }
  }
  function restoreIsolation(){
    outsideInert.forEach(function(value,element){element.inert=value;});
    outsideInert=new Map();
  }
  function setMenuOpen(requested,restoreFocus){
    menuOpen=mobileLayout.matches&&Boolean(requested);
    restoreIsolation();
    listContainer.inert=false;
    listContainer.removeAttribute('aria-hidden');
    document.body.classList.toggle('spell-menu-open',menuOpen);
    mobileMenuButton.setAttribute('aria-expanded',String(menuOpen));
    mobileBackdrop.hidden=!menuOpen;
    if(menuOpen){
      listContainer.setAttribute('role','dialog'); listContainer.setAttribute('aria-modal','true');
      var current=listContainer;
      while(current&&current!==document.body){
        Array.from(current.parentElement.children).forEach(function(sibling){
          if(sibling===current||/^(SCRIPT|STYLE|LINK)$/.test(sibling.tagName)) return;
          outsideInert.set(sibling,sibling.inert); sibling.inert=true;
        });
        current=current.parentElement;
      }
      fBusca.focus();
    } else {
      listContainer.removeAttribute('role'); listContainer.removeAttribute('aria-modal');
      listContainer.inert=mobileLayout.matches;
      if(listContainer.inert) listContainer.setAttribute('aria-hidden','true');
      if(restoreFocus&&mobileLayout.matches) mobileMenuButton.focus();
    }
  }
  function closeMenu(restoreFocus){setMenuOpen(false,restoreFocus!==false);}
  function handleLayout(){
    var hadFocus=listContainer.contains(document.activeElement);
    closeMenu(false);
    mobileMenuButton.hidden=!mobileLayout.matches; mobileClose.hidden=!mobileLayout.matches; mobileApply.hidden=!mobileLayout.matches;
    if(mobileLayout.matches&&hadFocus) mobileMenuButton.focus();
  }
  function trapMenuFocus(event){
    var controls=Array.from(listContainer.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),a[href],summary'))
      .filter(function(control){return control.tabIndex>=0&&control.getClientRects().length&&!control.closest('[inert]');});
    var first=controls[0],last=controls[controls.length-1];
    if(event.shiftKey&&(document.activeElement===first||!listContainer.contains(document.activeElement))){event.preventDefault();last.focus();}
    else if(!event.shiftKey&&(document.activeElement===last||!listContainer.contains(document.activeElement))){event.preventDefault();first.focus();}
  }

  document.body.classList.add('spells-enhanced');
  listContainer.querySelectorAll('input,select,button').forEach(function(control){control.disabled=false;});
  selectFromUrl(); handleLayout();
  fBusca.addEventListener('input',function(){applyFilters(true);});
  [fClasse,fEscola,fNivel,fConc,fRitual].forEach(function(control){control.addEventListener('change',function(){applyFilters(false);});});
  document.querySelectorAll('[data-school-filter]').forEach(function(button){button.addEventListener('click',function(){
    fEscola.value=fEscola.value===button.dataset.schoolFilter?'':button.dataset.schoolFilter; applyFilters(false);
  });});
  clearFilters.addEventListener('click',function(){
    fBusca.value=fClasse.value=fEscola.value=fNivel.value=''; fConc.checked=fRitual.checked=false;
    applyFilters(false); fBusca.focus({preventScroll:true});
  });
  backToDeck.addEventListener('click',function(event){
    if(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||event.button!==0) return;
    event.preventDefault(); selectedSlug=null; render(); syncFiltersToUrl(false);
    mount.querySelector('h2').focus({preventScroll:true}); deckTitle.scrollIntoView({block:'start'});
  });
  resultsContainer.addEventListener('click',function(event){
    var link=event.target.closest('a[data-slug]');
    if(!link||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||event.button!==0) return;
    event.preventDefault(); selectMagia(link.dataset.slug);
  });
  mount.addEventListener('click',function(event){
    if(!event.target.closest('[data-guide-start]')) return;
    if(mobileLayout.matches) setMenuOpen(true,false); else fBusca.focus();
  });
  [[previousSpell,-1],[nextSpell,1]].forEach(function(pair){pair[0].addEventListener('click',function(){
    var position=filtered.findIndex(function(m){return m.slug===selectedSlug;});
    var next=filtered[position+pair[1]]; if(next) selectMagia(next.slug);
  });});
  mobileMenuButton.addEventListener('click',function(){setMenuOpen(!menuOpen,true);});
  [mobileClose,mobileBackdrop].forEach(function(button){button.addEventListener('click',function(){closeMenu();});});
  mobileApply.addEventListener('click',function(){closeMenu(false);deckTitle.focus({preventScroll:true});deckTitle.scrollIntoView({block:'start'});});
  mobileLayout.addEventListener('change',handleLayout);
  document.addEventListener('keydown',function(event){
    if(event.key==='Escape'&&menuOpen){event.preventDefault();closeMenu();}
    else if(event.key==='Tab'&&menuOpen) trapMenuFocus(event);
  });
  window.addEventListener('popstate',selectFromUrl);
  window.addEventListener('hashchange',selectFromUrl);
})();
