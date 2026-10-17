/* Navigation only: native purchase/cancel POSTs and all server guards stay intact. */
(() => {
  const norm=value=>String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const matches=(entry,area,query,rarity)=>entry.area===area&&norm(entry.search).includes(norm(query))&&(!rarity||entry.rarity===rarity);
  if(typeof module!=='undefined'&&module.exports)module.exports={norm,matches};
  if(typeof document==='undefined')return;
  const root=document.querySelector('.nt-page');if(!root)return;
  const search=root.querySelector('#nt-search'),rarity=root.querySelector('#nt-rarity'),areaInput=root.querySelector('#nt-area');
  const tabs=[...root.querySelectorAll('[data-nt-area]')],links=[...root.querySelectorAll('.nt-item')],panels=[...root.querySelectorAll('.nt-offer')];
  const reader=root.querySelector('#nt-reader'),empty=root.querySelector('#nt-reader-empty'),listEmpty=root.querySelector('#nt-list-empty');
  const count=root.querySelector('#nt-count'),countLabel=root.querySelector('#nt-count-label'),announce=root.querySelector('#nt-announcement');
  if(!search||!rarity||!areaInput||!reader)return;
  let area=root.dataset.area,selected=root.dataset.selected;
  const modified=event=>event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey;
  function address(key=selected,scope=area,clear=false){
    const url=new URL(location.href);url.searchParams.set('area',scope);url.searchParams.delete('m');url.hash='';
    if(key)url.searchParams.set('anuncio',key);else url.searchParams.delete('anuncio');
    if(!clear&&search.value.trim())url.searchParams.set('q',search.value.trim().slice(0,160));else url.searchParams.delete('q');
    if(!clear&&rarity.value)url.searchParams.set('raridade',rarity.value);else url.searchParams.delete('raridade');
    return url.pathname+url.search;
  }
  function refresh(requested=selected){
    if(!tabs.some(tab=>tab.dataset.ntArea===area))area='venda';
    const visible=links.filter(link=>{const yes=matches(link.dataset,area,search.value.trim(),rarity.value);link.hidden=!yes;return yes;});
    selected=visible.some(link=>link.dataset.key===requested)?requested:(visible[0]?.dataset.key||'');
    areaInput.value=area;root.dataset.area=area;root.dataset.selected=selected;
    panels.forEach(panel=>panel.hidden=panel.id!=='nt-offer-'+selected);
    tabs.forEach(tab=>{const yes=tab.dataset.ntArea===area;if(yes)tab.setAttribute('aria-current','page');else tab.removeAttribute('aria-current');tab.href=address('',tab.dataset.ntArea);});
    links.forEach(link=>{const yes=link.dataset.key===selected;link.classList.toggle('is-active',yes);if(yes)link.setAttribute('aria-current','true');else link.removeAttribute('aria-current');link.href=address(link.dataset.key,link.dataset.area);});
    empty.hidden=visible.length>0;listEmpty.hidden=visible.length>0;count.textContent=String(visible.length);
    countLabel.textContent=visible.length===1?'anúncio encontrado':'anúncios encontrados';
    root.querySelector('#nt-empty-scope').textContent=area==='meus'?'Meus anúncios':'Vitrine da comunidade';
    root.querySelectorAll('.nt-clear').forEach(link=>{link.hidden=!search.value&&!rarity.value;link.href=address('',area,true);});
    announce.textContent=`${visible.length} ${countLabel.textContent}. ${selected?links.find(l=>l.dataset.key===selected).querySelector('strong').textContent+' selecionado.':''}`;
  }
  function sync(push=false){const url=address();if(url!==location.pathname+location.search)(push?history.pushState:history.replaceState).call(history,null,'',url);}
  root.querySelector('.nt-filter').addEventListener('submit',event=>{event.preventDefault();refresh();sync();});
  search.addEventListener('input',()=>{refresh();sync();});rarity.addEventListener('change',()=>{refresh();sync();});
  tabs.forEach(tab=>tab.addEventListener('click',event=>{if(modified(event))return;event.preventDefault();area=tab.dataset.ntArea;refresh('');sync(true);}));
  links.forEach(link=>link.addEventListener('click',event=>{if(modified(event))return;event.preventDefault();refresh(link.dataset.key);sync(true);reader.focus({preventScroll:true});if(matchMedia('(max-width:800px)').matches)reader.scrollIntoView({block:'start',behavior:'instant'});}));
  root.querySelectorAll('.nt-clear').forEach(link=>link.addEventListener('click',event=>{if(modified(event))return;event.preventDefault();search.value='';rarity.value='';refresh('');sync();search.focus({preventScroll:true});}));
  const guide=root.querySelector('#nt-guide');root.querySelector('.nt-hero a[href="#nt-guide"]').addEventListener('click',()=>{guide.open=true;});
  addEventListener('popstate',()=>{const params=new URL(location.href).searchParams;area=params.get('area')||'venda';search.value=(params.get('q')||'').slice(0,160);rarity.value=params.get('raridade')||'';refresh(params.get('anuncio')||'');});
  refresh();
})();
