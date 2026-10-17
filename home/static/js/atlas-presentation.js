/* Additive UI only. Does not replace any map/editor function or persist data. */
(() => {
  const shell=document.querySelector('.bft-atlas .map-shell');
  if(!shell || typeof map==='undefined' || typeof markersLayer==='undefined')return;
  const search=document.getElementById('mapSearch'),category=document.getElementById('categoryFilter');
  const status=document.getElementById('atlasFilterStatus'),layerStatus=document.getElementById('atlasLayerStatus');
  const layerCount=document.getElementById('atlasLayerCount'),clear=document.getElementById('atlasClearFilters');
  const empty=document.getElementById('atlasNoResults'),emptyTitle=document.getElementById('atlasEmptyTitle'),emptyCopy=document.getElementById('atlasEmptyCopy');
  const emptyClear=document.getElementById('atlasEmptyClear'),toggle=document.getElementById('sidebarToggle');
  const help=document.getElementById('atlasHelp'),overview=document.getElementById('atlasOverview');
  let queued=false;
  const text=(node,value)=>{if(node && node.textContent!==value)node.textContent=value;};
  function positionMobilePopup(){
    if(!window.matchMedia('(max-width:1100px)').matches)return;
    const popup=document.querySelector('.mobile-leaflet-popup'),frame=document.getElementById('map');
    if(!popup||!frame)return;
    const viewport=frame.getBoundingClientRect();
    const selector=document.querySelector('.map-layer-selector');
    const selectorBottom=selector?.getBoundingClientRect().bottom||viewport.top;
    const top=Math.max(viewport.top+12,Math.min(selectorBottom+12,viewport.top+110));
    // Keep Leaflet's anchoring/close control; translate only the rendered card.
    popup.style.setProperty('--atlas-popup-max-height',Math.max(80,viewport.bottom-top-12)+'px');
    const previous=parseFloat(popup.style.getPropertyValue('--atlas-popup-shift-y'))||0;
    const rect=popup.getBoundingClientRect(),naturalTop=rect.top-previous;
    const target=Math.min(Math.max(naturalTop,top),Math.max(top,viewport.bottom-12-rect.height));
    popup.style.setProperty('--atlas-popup-shift-y',(target-naturalTop)+'px');
  }
  function update(){
    queued=false;
    const layer=layersData.find(row=>row.id_layer===activeLayer);
    const total=leafletMarkers.filter(marker=>(marker._bonfireData.camada||0)===activeLayer).length;
    const shown=markersLayer.getLayers().length;
    const filtered=Boolean(search.value.trim()||category.value);
    text(layerStatus,layer?.nome||'Camada '+activeLayer);
    text(layerCount,total+' '+(total===1?'local nesta camada':'locais nesta camada'));
    text(status,shown+' '+(shown===1?'pino exibido':'pinos exibidos')+(filtered?' de '+total:''));
    clear.hidden=!filtered;
    empty.hidden=shown!==0;
    emptyClear.hidden=!filtered;
    text(emptyTitle,total===0?'Nenhum local nesta camada':'Nenhum pino encontrado');
    text(emptyCopy,total===0?'Esta camada ainda não tem pinos. Você pode explorar suas áreas ou trocar de camada.':'Tente outro nome ou limpe os filtros. Os territórios continuam disponíveis no mapa.');
    const open=shell.classList.contains('is-sidebar-open');
    const sidebar=document.getElementById('mapSidebar');
    if(sidebar)sidebar.inert=window.matchMedia('(max-width:1100px)').matches&&!open;
    toggle.setAttribute('aria-expanded',String(open));
    toggle.setAttribute('aria-label',open?'Fechar locais do mapa':'Abrir locais do mapa');
    document.querySelectorAll('.territory-group').forEach(group=>{
      const button=group.querySelector('.territory-button'),regions=group.querySelector('.territory-regions');
      const expanded=group.classList.contains('is-open');
      button?.setAttribute('aria-expanded',String(expanded));
      if(regions)regions.inert=!expanded;
    });
    document.querySelectorAll('.map-place-dots').forEach(dots=>{
      dots.setAttribute('role','img');
      dots.setAttribute('aria-label',dots.querySelectorAll('.filled').length+' de 5');
    });
    document.querySelectorAll('.map-detail-close').forEach(button=>button.setAttribute('aria-label','Fechar ficha do local'));
    document.querySelectorAll('.layer-selector-btn[data-layer-id]').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.layerId)===activeLayer)));
    document.querySelectorAll('.map-category-option').forEach(button=>button.setAttribute('aria-selected',String(button.dataset.value===category.value)));
    positionMobilePopup();
  }
  function schedule(){if(!queued){queued=true;requestAnimationFrame(update);}}
  function clearFilters(){
    search.value='';
    // Use the original category control, keeping its icon, label and filter routine.
    document.querySelector('.map-category-option[data-value=""]')?.click();
    search.dispatchEvent(new Event('input',{bubbles:true}));
    schedule();
  }
  clear.addEventListener('click',clearFilters);emptyClear.addEventListener('click',clearFilters);
  overview.addEventListener('click',()=>{
    // Camera only: no selection/filter clearing, draft reset, saving or layer switch.
    map.invalidateSize();map.fitBounds(bounds,{padding:[25,25],animate:false});
  });
  search.addEventListener('input',schedule);
  map.on('layeradd layerremove zoomend moveend popupopen resize',schedule);
  const observer=new MutationObserver(schedule);
  observer.observe(shell,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
  const categoryButton=document.getElementById('categoryFilterButton');
  const categoryWrap=document.getElementById('categoryFilterWrap');
  categoryWrap.addEventListener('keydown',event=>{
    const options=Array.from(categoryWrap.querySelectorAll('.map-category-option'));
    if(event.key==='Escape'){
      categoryWrap.classList.remove('is-open');categoryButton.setAttribute('aria-expanded','false');categoryButton.focus();event.stopPropagation();
    }else if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
      event.preventDefault();categoryWrap.classList.add('is-open');categoryButton.setAttribute('aria-expanded','true');
      const current=options.indexOf(document.activeElement);
      const next=event.key==='Home'?0:event.key==='End'?options.length-1:event.key==='ArrowUp'?Math.max(0,current-1):Math.min(options.length-1,current+1);
      options[next]?.focus();
    }
  });
  document.addEventListener('keydown',event=>{
    if(event.key!=='Escape')return;
    if(help.open){help.open=false;help.querySelector('summary').focus();return;}
    // Escape closes the mobile index, never an editor draft or pending changes.
    if(shell.classList.contains('is-sidebar-open')){shell.classList.remove('is-sidebar-open');toggle.focus();schedule();}
  });
  document.addEventListener('click',event=>{if(help.open&&!help.contains(event.target))help.open=false;});
  window.addEventListener('resize',()=>{map.invalidateSize();schedule();});
  update();
})();
