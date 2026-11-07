// Add click/touch/keyboard support without replacing the original hover menus.
document.addEventListener('DOMContentLoaded',()=>{
  const header=document.querySelector('.bft-restored-header');
  if(!header)return;
  const entries=[...header.querySelectorAll('[class~="group/tab"],[class~="group/user"]')].map((root,index)=>{
    const button=root.querySelector(':scope > button'),panel=root.querySelector(':scope > div');
    if(!button||!panel)return null;
    panel.id=panel.id||'bft-nav-panel-'+index;
    button.type='button';button.setAttribute('aria-controls',panel.id);button.setAttribute('aria-expanded','false');
    return {root,button,panel,pinned:false,closeTimer:null};
  }).filter(Boolean);
  function close(item){clearTimeout(item.closeTimer);item.closeTimer=null;item.pinned=false;item.root.dataset.navOpen='false';item.button.setAttribute('aria-expanded','false');}
  function open(item){clearTimeout(item.closeTimer);item.closeTimer=null;entries.forEach(other=>{if(other!==item)close(other);});item.root.dataset.navOpen='true';item.button.setAttribute('aria-expanded','true');}
  entries.forEach(item=>{
    item.root.addEventListener('pointerenter',()=>open(item));
    // Let a pointer cross the compact shortcut row without losing its menu.
    item.root.addEventListener('pointerleave',()=>{if(!item.pinned){clearTimeout(item.closeTimer);item.closeTimer=setTimeout(()=>close(item),250);}});
    item.button.addEventListener('click',()=>{item.pinned=!item.pinned;if(item.pinned)open(item);else close(item);});
    item.root.addEventListener('focusin',()=>open(item));
    item.root.addEventListener('focusout',event=>{if(!item.root.contains(event.relatedTarget))close(item);});
    item.button.addEventListener('keydown',event=>{if(event.key==='ArrowDown'){event.preventDefault();item.pinned=true;open(item);item.panel.querySelector('a')?.focus();}});
    item.root.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();item.button.focus();entries.forEach(close);}});
    item.panel.addEventListener('click',event=>{if(event.target.closest('a'))entries.forEach(close);});
  });
  document.addEventListener('click',event=>{if(!entries.some(item=>item.root.contains(event.target)))entries.forEach(close);});
  window.matchMedia('(max-width:1099px)').addEventListener('change',()=>entries.forEach(close));
  header.querySelectorAll('.bft-quick-access a').forEach(link=>{
    if(new URL(link.href,location.href).pathname===location.pathname)link.setAttribute('aria-current','page');
  });
});
