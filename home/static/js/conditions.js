/* Progressive reference reader: no application of conditions or writes. */
(() => {
  const list=document.getElementById('co-list'),reader=document.getElementById('co-reader');
  if(!list || !reader)return;
  const links=Array.from(list.querySelectorAll('.co-item'));
  const panels=Array.from(reader.querySelectorAll('.co-panel'));
  const search=document.getElementById('co-search'),active=document.getElementById('co-active');
  const count=document.getElementById('co-count'),announcement=document.getElementById('co-announcement');
  const listEmpty=document.getElementById('co-list-empty'),readerEmpty=document.getElementById('co-reader-empty');
  const clears=Array.from(document.querySelectorAll('.co-clear'));
  const references=Array.from(document.querySelectorAll('[data-condition-reference]'));
  const norm=value=>String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const nativeClick=event=>event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button!==0;
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
      link.hidden=!norm(link.dataset.search).includes(norm(query));
      const url=new URL(link.href,location.href);
      if(query)url.searchParams.set('q',query);else url.searchParams.delete('q');
      link.href=url.pathname+url.search+url.hash;
    });
    const results=visible();count.textContent=String(results.length);listEmpty.hidden=results.length>0;
    clears.forEach(link=>link.hidden=!query);
    if(!show(selected,updateUrl,false) && results.length)show(results[0].dataset.target,updateUrl,false);
    if(!results.length){
      selected='';active.value='';panels.forEach(panel=>panel.hidden=true);readerEmpty.hidden=false;
      if(updateUrl){const url=new URL(location.href);url.searchParams.delete('condicao');url.hash='';if(query)url.searchParams.set('q',query);else url.searchParams.delete('q');history.replaceState(null,'',url.pathname+url.search);}
    }
    if(updateUrl)announcement.textContent=results.length+' condição(ões) encontrada(s).';
  }
  function bringReader(force=false){if(force || window.matchMedia('(max-width:760px)').matches){reader.focus({preventScroll:true});reader.scrollIntoView({block:'start',behavior:'auto'});}}
  search.addEventListener('input',()=>filter(true));
  search.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();search.value='';filter(true);}});
  clears.forEach(link=>link.addEventListener('click',event=>{if(nativeClick(event))return;event.preventDefault();search.value='';filter(true);search.focus();}));
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
    event.preventDefault();search.value='';filter();show(id,true);bringReader(true);
  }));
  function fromLocation(){const id=location.hash.slice(1);if(panels.some(panel=>panel.id===id))show(id,false,false);}
  filter();fromLocation();
  window.addEventListener('hashchange',fromLocation);
  window.addEventListener('popstate',()=>{search.value=new URL(location.href).searchParams.get('q') || '';filter();fromLocation();});
})();
