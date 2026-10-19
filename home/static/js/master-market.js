/* Navigation/filtering only. Economy operations remain native, CSRF-protected POSTs. */
(() => {
  const root=document.querySelector('.mm-page');
  if(!root)return;
  const tabs=Array.from(root.querySelectorAll('[data-mm-area]'));
  const areas=Array.from(root.querySelectorAll('.mm-area'));
  const links=Array.from(root.querySelectorAll('.mm-item'));
  const panels=Array.from(root.querySelectorAll('.mm-reward'));
  const search=document.getElementById('mm-search'),kind=document.getElementById('mm-kind');
  const active=document.getElementById('mm-active'),count=document.getElementById('mm-count');
  const reader=document.getElementById('mm-reader'),empty=document.getElementById('mm-reader-empty');
  const listEmpty=document.getElementById('mm-list-empty'),announcement=document.getElementById('mm-announcement');
  const clears=Array.from(root.querySelectorAll('.mm-clear'));
  if(!search||!kind||!active||!reader)return;
  const norm=value=>String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const native=event=>event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey;
  let selected=active.value;
  let area=tabs.find(tab=>tab.getAttribute('aria-current')==='page')?.dataset.mmArea||'recompensas';
  function setArea(key,update=false){
    if(!tabs.some(tab=>tab.dataset.mmArea===key))key='recompensas';
    area=key;
    areas.forEach(panel=>panel.hidden=panel.id!=='mm-area-'+key);
    tabs.forEach(tab=>{const chosen=tab.dataset.mmArea===key;tab.classList.toggle('is-active',chosen);if(chosen)tab.setAttribute('aria-current','page');else tab.removeAttribute('aria-current');});
    if(update)syncUrl('push');
  }
  function syncUrl(mode='replace'){
    const url=new URL(location.href);
    url.searchParams.set('area',area);url.searchParams.delete('m');
    if(selected)url.searchParams.set('recompensa',selected);else url.searchParams.delete('recompensa');
    if(search.value.trim())url.searchParams.set('q',search.value.trim().slice(0,160));else url.searchParams.delete('q');
    if(kind.value)url.searchParams.set('tipo',kind.value);else url.searchParams.delete('tipo');
    url.hash='';
    const next=url.pathname+url.search;
    if(next===location.pathname+location.search+location.hash)return;
    history[mode==='push'?'pushState':'replaceState'](history.state,'',next);
  }
  function show(key){
    const link=links.find(node=>node.dataset.key===key&&!node.hidden);
    if(!link)return false;
    selected=key;active.value=key;empty.hidden=true;
    panels.forEach(panel=>panel.hidden=panel.id!==link.dataset.target);
    links.forEach(node=>{node.classList.toggle('is-active',node===link);if(node===link)node.setAttribute('aria-current','true');else node.removeAttribute('aria-current');});
    return true;
  }
  function filter(update=false){
    const query=search.value.trim().slice(0,160);
    links.forEach(link=>{
      link.hidden=!(norm(link.dataset.search).includes(norm(query))&&(!kind.value||link.dataset.kind===kind.value));
      const url=new URL(link.href,location.href);
      if(query)url.searchParams.set('q',query);else url.searchParams.delete('q');
      if(kind.value)url.searchParams.set('tipo',kind.value);else url.searchParams.delete('tipo');
      link.href=url.pathname+url.search+url.hash;
    });
    const visible=links.filter(link=>!link.hidden);
    count.textContent=String(visible.length);listEmpty.hidden=visible.length>0;
    clears.forEach(link=>link.hidden=!query&&!kind.value);
    if(!show(selected)&&visible.length)show(visible[0].dataset.key);
    if(!visible.length){selected='';active.value='';panels.forEach(panel=>panel.hidden=true);links.forEach(link=>{link.classList.remove('is-active');link.removeAttribute('aria-current');});empty.hidden=false;}
    if(update){syncUrl();announcement.textContent=visible.length+' recompensa(s) encontrada(s).';}
  }
  tabs.forEach(tab=>tab.addEventListener('click',event=>{if(native(event))return;event.preventDefault();setArea(tab.dataset.mmArea,true);announcement.textContent='Área '+tab.textContent.trim()+' aberta.';}));
  links.forEach(link=>{
    link.addEventListener('click',event=>{if(native(event)||!show(link.dataset.key))return;event.preventDefault();syncUrl('push');announcement.textContent='Recompensa selecionada: '+link.querySelector('strong').textContent+'.';if(window.matchMedia('(max-width:760px)').matches){reader.focus({preventScroll:true});reader.scrollIntoView({block:'start',behavior:'auto'});}});
    link.addEventListener('keydown',event=>{
      const visible=links.filter(node=>!node.hidden),index=visible.indexOf(link);
      const next=event.key==='ArrowDown'?Math.min(index+1,visible.length-1):event.key==='ArrowUp'?Math.max(index-1,0):event.key==='Home'?0:event.key==='End'?visible.length-1:null;
      if(next===null||next<0)return;event.preventDefault();visible[next].focus();show(visible[next].dataset.key);syncUrl('push');
    });
  });
  search.addEventListener('input',()=>filter(true));kind.addEventListener('change',()=>filter(true));
  search.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();search.value='';filter(true);}});
  clears.forEach(link=>link.addEventListener('click',event=>{if(native(event))return;event.preventDefault();search.value='';kind.value='';filter(true);search.focus();}));
  window.addEventListener('popstate',()=>{const url=new URL(location.href);search.value=url.searchParams.get('q')||'';kind.value=url.searchParams.get('tipo')||'';selected=url.searchParams.get('recompensa')||'';setArea(url.searchParams.get('area'));filter();});
  const review=document.getElementById('mm-review');
  const details=document.getElementById('mm-review-details');
  const title=document.getElementById('mm-review-title');
  const back=document.getElementById('mm-review-back');
  const confirm=document.getElementById('mm-review-confirm');
  if(review&&details&&title&&back&&confirm&&typeof review.showModal==='function'){
    let pending=null;
    let sending=false;
    const value=(form,name)=>form.elements.namedItem(name)?.value.trim()||'';
    function append(label,value){
      const dt=document.createElement('dt'),dd=document.createElement('dd');
      dt.textContent=label;dd.textContent=value||'Não informado';details.append(dt,dd);
    }
    root.querySelectorAll('form[data-mm-review]').forEach(form=>form.addEventListener('submit',event=>{
      if(sending)return;
      if(!form.reportValidity())return;
      event.preventDefault();
      const submitter=event.submitter||form.querySelector('button[type="submit"]');
      details.replaceChildren();
      if(form.dataset.mmReview==='eventos'){
        title.textContent='Revisar troca por Braseiros';
        append('Personagem',form.elements.namedItem('personagem').selectedOptions[0]?.textContent.trim());
        append('Moedas de Evento',value(form,'moedas'));
      }else if(form.dataset.mmReview==='registro'){
        title.textContent='Revisar registro de mesa';
        append('Aventura',value(form,'nome'));
        append('Data',value(form,'data'));
        append('Jogadores',value(form,'jogadores'));
        append('Crédito em MM',value(form,'recompensa_mm'));
        append('Observação',value(form,'observacao'));
      }else{
        title.textContent='Revisar recompensa';
        const reward=form.closest('.mm-reward');
        append('Ação',submitter?.textContent.trim());
        append('Recompensa',reward?.querySelector('h2')?.textContent.trim());
        append('Custo exibido',reward?.querySelector('.mm-price')?.textContent.trim());
      }
      pending={form,submitter};
      review.showModal();
    }));
    back.addEventListener('click',()=>review.close());
    review.addEventListener('click',event=>{if(event.target===review)review.close();});
    review.addEventListener('close',()=>{
      const submitter=pending?.submitter;
      pending=null;
      if(!sending)submitter?.focus();
    });
    confirm.addEventListener('click',()=>{
      if(!pending)return;
      const {form,submitter}=pending;
      if(!form.reportValidity()){review.close();return;}
      sending=true;
      confirm.disabled=true;
      form.requestSubmit(submitter);
    });
  }
  filter();
})();
