/* Progressive reference reader: no application of conditions or writes. */
(() => {
  const list=document.getElementById('co-list'),reader=document.getElementById('co-reader');
  if(!list || !reader)return;
  const links=Array.from(list.querySelectorAll('.co-item'));
  const panels=Array.from(reader.querySelectorAll('.co-panel'));
  const search=document.getElementById('co-search'),category=document.getElementById('co-category'),active=document.getElementById('co-active');
  const count=document.getElementById('co-count'),announcement=document.getElementById('co-announcement');
  const listEmpty=document.getElementById('co-list-empty'),readerEmpty=document.getElementById('co-reader-empty');
  const clears=Array.from(document.querySelectorAll('.co-clear'));
  const conditionNames=panels.map(panel=>({id:panel.id,name:panel.querySelector('h2')?.textContent.trim() || ''}));
  const normalized=value=>String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  for(const panel of panels){
    const body=panel.querySelector('.co-panel-body');
    if(!body)continue;
    const text=normalized(Array.from(body.querySelectorAll('.co-effect p')).map(effect=>effect.textContent).join(' '));
    const related=conditionNames.filter(item=>{
      if(!item.name || item.id===panel.id)return false;
      const name=normalized(item.name).replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
      return new RegExp('(?:^|[^\\p{L}\\p{N}])'+name+'(?=$|[^\\p{L}\\p{N}])','u').test(text);
    });
    if(!related.length)continue;
    const section=document.createElement('section');
    section.className='co-related';
    const heading=document.createElement('h3');
    heading.textContent='Condições citadas';
    const nav=document.createElement('nav');
    nav.setAttribute('aria-label','Condições citadas em '+panel.querySelector('h2').textContent.trim());
    for(const item of related){
      const link=document.createElement('a');
      link.href='#'+item.id;
      link.dataset.conditionReference='';
      link.textContent=item.name+' ↗';
      nav.appendChild(link);
    }
    section.append(heading,nav);
    body.appendChild(section);
  }
  const references=Array.from(document.querySelectorAll('[data-condition-reference]'));
  const norm=normalized;
  const nativeClick=event=>event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button!==0;
  const categories=[...new Set(links.map(link=>link.dataset.category).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'pt-BR'));
  for(const value of categories){const option=document.createElement('option');option.value=value;option.textContent=value==='5e'?'Regras do sistema · 5e':value==='homebrew'?'Regras da casa':value;category.appendChild(option);}
  category.disabled=false;
  category.hidden=categories.length<2;
  document.querySelector('label[for="co-category"]').hidden=categories.length<2;
  category.value=categories.includes(new URL(location.href).searchParams.get('categoria'))?new URL(location.href).searchParams.get('categoria'):'';
  let selected=links.find(link=>link.getAttribute('aria-current')==='true')?.dataset.target || '';
  const visible=()=>links.filter(link=>!link.hidden);
  function show(id,updateUrl=false,announce=true){
    const link=links.find(item=>item.dataset.target===id && !item.hidden);
    const panel=panels.find(item=>item.id===id);
    if(!link || !panel)return false;
    panels.forEach(item=>item.hidden=item!==panel);
    links.forEach(item=>{item.classList.toggle('is-active',item===link);if(item===link)item.setAttribute('aria-current','true');else item.removeAttribute('aria-current');});
    selected=id;active.value=id.slice(5);readerEmpty.hidden=true;
    if(updateUrl)history.replaceState(null,'',link.href);
    if(announce)announcement.textContent='Condição '+panel.querySelector('h2').textContent.trim()+' selecionada.';
    return true;
  }
  function filter(updateUrl=false){
    const query=search.value.slice(0,160).trim();
    links.forEach(link=>{
      link.hidden=!!(category.value && link.dataset.category!==category.value) || !norm(link.dataset.search).includes(norm(query));
      const url=new URL(link.href,location.href);
      if(query)url.searchParams.set('q',query);else url.searchParams.delete('q');
      if(category.value)url.searchParams.set('categoria',category.value);else url.searchParams.delete('categoria');
      link.href=url.pathname+url.search+url.hash;
    });
    const results=visible();count.textContent=String(results.length);listEmpty.hidden=results.length>0;
    clears.forEach(link=>link.hidden=!query && !category.value);
    if(!show(selected,updateUrl,false) && results.length)show(results[0].dataset.target,updateUrl,false);
    if(!results.length){
      selected='';active.value='';panels.forEach(panel=>panel.hidden=true);readerEmpty.hidden=false;
      if(updateUrl){const url=new URL(location.href);url.searchParams.delete('condicao');url.hash='';if(query)url.searchParams.set('q',query);else url.searchParams.delete('q');if(category.value)url.searchParams.set('categoria',category.value);else url.searchParams.delete('categoria');history.replaceState(null,'',url.pathname+url.search);}
    }
    if(updateUrl)announcement.textContent=results.length+' condição(ões) encontrada(s).';
  }
  function bringReader(force=false){if(force || window.matchMedia('(max-width:760px)').matches){reader.focus({preventScroll:true});reader.scrollIntoView({block:'start',behavior:'auto'});}}
  search.addEventListener('input',()=>filter(true));
  category.addEventListener('change',()=>filter(true));
  search.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();search.value='';filter(true);}});
  clears.forEach(link=>link.addEventListener('click',event=>{if(nativeClick(event))return;event.preventDefault();search.value='';category.value='';filter(true);search.focus();}));
  links.forEach(link=>{
    link.addEventListener('click',event=>{if(nativeClick(event) || !show(link.dataset.target,true))return;event.preventDefault();bringReader();});
    link.addEventListener('keydown',event=>{
      const items=visible(),index=items.indexOf(link);
      const next=event.key==='ArrowDown'?Math.min(index+1,items.length-1):event.key==='ArrowUp'?Math.max(index-1,0):event.key==='Home'?0:event.key==='End'?items.length-1:null;
      if(next===null || next<0)return;
      event.preventDefault();items[next].focus();show(items[next].dataset.target,true);
    });
  });
  references.forEach(link=>link.addEventListener('click',event=>{
    if(nativeClick(event))return;
    const id=new URL(link.href,location.href).hash.slice(1);
    if(!links.some(item=>item.dataset.target===id))return;
    event.preventDefault();search.value='';category.value='';filter();show(id,true);bringReader(true);
  }));
  function fromLocation(){
    const id=location.hash.slice(1);
    if(panels.some(panel=>panel.id===id) && show(id,false,false))bringReader(true);
  }
  filter();fromLocation();
  window.addEventListener('pageshow',()=>{if(location.hash)fromLocation();});
  window.addEventListener('hashchange',fromLocation);
  window.addEventListener('popstate',()=>{const params=new URL(location.href).searchParams;search.value=params.get('q') || '';category.value=categories.includes(params.get('categoria'))?params.get('categoria'):'';filter();fromLocation();});
})();
