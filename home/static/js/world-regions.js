/* Additive presentation only: no lore, geometry, permissions or saves here. */
(function(root){
 'use strict';
 const normalize=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();
 const matches=(text,query)=>normalize(query).split(' ').every(word=>normalize(text).includes(word));
 const focusAvailable=node=>!node.disabled&&!!node.getClientRects().length&&!node.closest('[hidden]')&&(!node.closest('details:not([open])')||node.tagName==='SUMMARY');
 if(typeof module!=='undefined')module.exports={normalize,matches,focusAvailable};
 if(typeof document==='undefined')return;
 function init(){
  const catalogue=document.getElementById('regionsCatalog');
  const search=document.getElementById('regionsSearch');
  if(catalogue&&search){
   const cards=Array.from(catalogue.querySelectorAll('[data-world-card]'));
   const clear=document.getElementById('regionsClearSearch');
   const status=document.getElementById('regionsResultCount');
   const savedOpen=new Map();let lastQuery='';
   function filter(){
    if(search.value&&!lastQuery)cards.forEach(card=>{const details=card.querySelector('details');if(details)savedOpen.set(details,details.open);});
    let total=0,places=0;
    cards.forEach(card=>{
     const visible=matches(card.textContent,search.value);card.hidden=!visible;
     if(visible){total++;places+=Number(card.dataset.localCount)||0;}
     let foundPlace=false;
     card.querySelectorAll('[data-world-place]').forEach(link=>{const found=!!search.value&&matches(link.textContent,search.value);link.classList.toggle('world-search-match',found);if(found)foundPlace=true;});
     const details=card.querySelector('details');if(details&&search.value)details.open=foundPlace;
    });
    if(!search.value){savedOpen.forEach((open,details)=>{details.open=open;});savedOpen.clear();}lastQuery=search.value;
    if(status)status.textContent=`${total} território${total===1?'':'s'} · ${places} locais conhecidos`;
    if(clear)clear.hidden=!search.value;
    const empty=document.getElementById('regionsEmptySearch');if(empty)empty.hidden=total>0||!cards.length;
   }
   search.addEventListener('input',filter);
   clear?.addEventListener('click',()=>{search.value='';filter();search.focus();});
  }
  const layout=document.querySelector('.region-layout');if(!layout)return;
  const searches=Array.from(layout.querySelectorAll('[data-world-index-search]'));
  let query='';const previousOpen=new Map();
  function filterIndex(){
   const layer=layout.querySelector('[data-layer-filter]')?.value||'';
   layout.querySelectorAll('.region-left,.region-mobile-drawer').forEach(index=>{
    let places=0,territories=0;
    index.querySelectorAll('details.territory-nav').forEach(group=>{
     const inLayer=!layer||String(group.dataset.navLayer)===layer;
     const name=group.querySelector('[data-territory-title]')?.textContent||'';
     const whole=matches(name,query);
     let count=0;
     group.querySelectorAll('[data-region-link]').forEach(link=>{
      const visible=inLayer&&(whole||matches(link.textContent,query));
      link.hidden=!visible;if(visible)count++;
     });
     const visible=inLayer&&(whole||count>0);group.hidden=!visible;
     if(visible){territories++;places+=count;}
     if(query&&visible)group.open=true;
    });
    const status=index.querySelector('[data-world-index-status]');
    if(status)status.textContent=territories?`${territories} território${territories===1?'':'s'} · ${places} localidade${places===1?'':'s'}`:'Nenhum lugar encontrado nesta camada.';
   });
  }
  searches.forEach(input=>input.addEventListener('input',()=>{
   const next=input.value;
   if(!query&&next)layout.querySelectorAll('details.territory-nav').forEach(group=>previousOpen.set(group,group.open));
   query=next;searches.forEach(other=>{if(other!==input)other.value=next;});
   if(!query){previousOpen.forEach((open,group)=>{group.open=open;});previousOpen.clear();}
   filterIndex();
  }));
  layout.querySelectorAll('[data-layer-filter]').forEach(select=>select.addEventListener('change',filterIndex));
  const drawer=document.getElementById('regionMobileDrawer');
  const opener=document.getElementById('regionMobileMenuButton');
  const mobile=root.matchMedia('(max-width:1100px)');
  function syncDrawer(){
   const open=mobile.matches&&document.body.classList.contains('region-menu-open');
   const wasOpen=opener?.getAttribute('aria-expanded')==='true';
   drawer.inert=!open;drawer.setAttribute('aria-hidden',String(!open));
   if(open){drawer.setAttribute('role','dialog');drawer.setAttribute('aria-modal','true');}
   else{drawer.removeAttribute('role');drawer.removeAttribute('aria-modal');}
   opener?.setAttribute('aria-expanded',String(open));
   if(open&&!wasOpen)document.getElementById('regionMobileClose')?.focus();
   if(!open&&wasOpen&&drawer.contains(document.activeElement))opener?.focus();
  }
  document.addEventListener('keydown',event=>{
   if(event.key!=='Tab'||drawer.inert)return;
   const focusable=Array.from(drawer.querySelectorAll('a[href],button,input,select,summary')).filter(focusAvailable);
   const first=focusable[0],last=focusable[focusable.length-1];
   if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
   else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
  });
  new MutationObserver(syncDrawer).observe(document.body,{attributes:true,attributeFilter:['class']});
  mobile.addEventListener('change',syncDrawer);syncDrawer();filterIndex();
  function syncArticle(){
   const title=document.getElementById('articleTitle')?.textContent;if(title)document.title=title+' · Bonfire Tales RPG';
   const mobileMap=layout.querySelector('[data-world-mobile-map]'),map=layout.querySelector('.map-pin-link');
   if(mobileMap&&map){mobileMap.href=map.href;mobileMap.hidden=map.style.display==='none';}
   const mobileChronicles=layout.querySelector('[data-world-mobile-chronicles]'),chronicles=document.getElementById('sideCronicasBtn');
   if(mobileChronicles&&chronicles)mobileChronicles.href=chronicles.href;
   layout.querySelectorAll('[data-region-link]').forEach(link=>{
    if(link.classList.contains('is-active'))link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
   });
   layout.querySelectorAll('[data-topic-toggle],[data-subtopic-toggle]').forEach(button=>button.setAttribute('aria-pressed',String(button.classList.contains('is-active'))));
   layout.querySelectorAll('.stat-item').forEach(item=>{
    const label=item.querySelector('.stat-label')?.textContent;
    const bar=item.querySelector('[data-target-width]');
    if(label&&bar){const val=parseFloat(bar.dataset.targetWidth)/20;item.setAttribute('aria-label',`${label}: ${val} de 5`);}
   });
  }
  new MutationObserver(syncArticle).observe(layout,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
  syncArticle();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})(typeof window!=='undefined'?window:globalThis);
