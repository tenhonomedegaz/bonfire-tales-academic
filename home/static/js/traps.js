/* Select pre-rendered references; never rolls, saves or edits trap rules. */
(() => {
  const list=document.getElementById('ar-list'), reader=document.getElementById('ar-reader');
  if (!list || !reader) return;
  const links=Array.from(list.querySelectorAll('.ar-item'));
  const panels=Array.from(reader.querySelectorAll('.ar-panel'));
  const search=document.getElementById('ar-busca'), active=document.getElementById('ar-active');
  const count=document.getElementById('ar-count'), announcement=document.getElementById('ar-announcement');
  const listEmpty=document.getElementById('ar-list-empty'), readerEmpty=document.getElementById('ar-reader-empty');
  const clearLinks=Array.from(document.querySelectorAll('.ar-clear-search'));
  let selected=links.find(link => link.getAttribute('aria-current')==='true')?.dataset.target || '';
  const norm=value => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const visible=() => links.filter(link => !link.hidden);
  function show(id,updateUrl=false,announce=true) {
    const link=links.find(item => item.dataset.target===id && !item.hidden);
    const panel=panels.find(item => item.id===id);
    if (!panel || !link) return false;
    panels.forEach(item => item.hidden=item!==panel);
    links.forEach(item => {
      item.classList.toggle('is-active',item===link);
      if (item===link) item.setAttribute('aria-current','true');
      else item.removeAttribute('aria-current');
    });
    selected=id;active.value=id.replace('armadilha-','');readerEmpty.hidden=true;
    if (updateUrl) history.replaceState(null,'',link.href);
    if (announce) announcement.textContent='Ficha de '+panel.querySelector('h2').textContent.trim()+' selecionada.';
    return true;
  }
  function filter(updateUrl=false) {
    const query=search.value.slice(0,160).trim();
    links.forEach(link => {
      link.hidden=!norm(link.dataset.search).includes(norm(query));
      const url=new URL(link.href,location.href);
      if (query) url.searchParams.set('q',query);else url.searchParams.delete('q');
      link.href=url.pathname+url.search+url.hash;
    });
    const results=visible();count.textContent=String(results.length);
    listEmpty.hidden=results.length>0;clearLinks.forEach(link => link.hidden=!query);
    if (!show(selected,updateUrl,false) && results.length) show(results[0].dataset.target,updateUrl,false);
    if (!results.length) {
      selected='';active.value='';panels.forEach(panel => panel.hidden=true);readerEmpty.hidden=false;
      if (links.length) readerEmpty.querySelector('h2').textContent='Nenhum perigo encontrado';
      if (updateUrl) {
        const url=new URL(location.href);url.searchParams.delete('active');url.hash='';
        if (query) url.searchParams.set('q',query);else url.searchParams.delete('q');
        history.replaceState(null,'',url.pathname+url.search);
      }
    }
    if (updateUrl) announcement.textContent=results.length+' resultado(s) para a busca.';
  }
  search.addEventListener('input',() => filter(true));
  search.addEventListener('keydown',event => {if(event.key==='Escape'){event.preventDefault();search.value='';filter(true);}});
  clearLinks.forEach(link => link.addEventListener('click',event => {
    if(event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button!==0)return;
    event.preventDefault();search.value='';filter(true);search.focus();
  }));
  links.forEach(link => {
    link.addEventListener('click',event => {
      if(event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button!==0)return;
      if(!show(link.dataset.target,true))return;
      event.preventDefault();
      if(window.matchMedia('(max-width:760px)').matches){reader.focus({preventScroll:true});reader.scrollIntoView({block:'start',behavior:'auto'});}
    });
    link.addEventListener('keydown',event => {
      const items=visible(),index=items.indexOf(link);
      const next=event.key==='ArrowDown'?Math.min(index+1,items.length-1):event.key==='ArrowUp'?Math.max(index-1,0):event.key==='Home'?0:event.key==='End'?items.length-1:null;
      if(next===null || next<0)return;
      event.preventDefault();items[next].focus();show(items[next].dataset.target,true);
    });
  });
  function fromLocation(){
    const hash=location.hash.slice(1);
    const panel=panels.filter(item => hash===item.id || hash.startsWith(item.id+'-'))
      .sort((a,b) => b.id.length-a.id.length)[0];
    if(panel)show(panel.id,false,false);
  }
  filter();fromLocation();
  window.addEventListener('hashchange',fromLocation);
  window.addEventListener('popstate',() => {search.value=new URL(location.href).searchParams.get('q') || '';filter();fromLocation();});
})();
