/* Old-page reading/navigation; purchases still belong to mercado_loja.js. */
(function () {
  'use strict';
  var checkout=document.getElementById('balcao-compra');
  var shop=document.querySelector('[data-shop-kind="mundano"]');
  var search=document.querySelector('[data-market-reference-search]');
  if (!checkout || !shop || !search) return;
  function normalize(value) { return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase(); }
  function filter() {
    var query=normalize(search.value.trim()),count=0;
    document.querySelectorAll('[data-market-reference-row]').forEach(function (row) {
      row.hidden=!!query && normalize(row.dataset.referenceSearch).indexOf(query)===-1;
      if (!row.hidden) count++;
    });
    document.querySelectorAll('[data-market-reference-section]').forEach(function (section) {
      section.hidden=!!query && !section.querySelector('[data-market-reference-row]:not([hidden])') && normalize(section.querySelector('h3').textContent).indexOf(query)===-1;
    });
    document.querySelectorAll('[data-market-reference-group]').forEach(function (group) {
      group.hidden=!!query && !group.querySelector('[data-market-reference-row]:not([hidden])') && normalize(group.textContent).indexOf(query)===-1;
    });
    document.querySelector('[data-market-reference-count]').textContent=count;
    document.querySelector('[data-market-reference-empty]').hidden=!query || !!document.querySelector('[data-market-reference-group]:not([hidden])');
  }
  document.querySelector('.market-reference-tools').hidden=false;
  search.addEventListener('input',filter);
  document.querySelector('[data-market-reference-reset]').addEventListener('click',function () { search.value=''; filter(); search.focus(); });
  document.querySelectorAll('.market-reference-sidebar nav a').forEach(function (link) {
    link.addEventListener('click',function () { if (search.value) { search.value=''; filter(); } });
  });
  checkout.addEventListener('toggle',function () {
    document.querySelector('.market-checkout-action').textContent=checkout.open?'Fechar balcão −':'Abrir balcão ＋';
  });
  document.addEventListener('click',function (event) {
    var link=event.target.closest('[data-market-open-counter],[data-market-catalog-jump]');
    if (!link) return;
    event.preventDefault();
    checkout.open=true;
    var target=link.getAttribute('data-market-catalog-jump');
    if (target) {
      shop.querySelector('[data-shop-tab="comprar"]')?.click();
      shop.querySelector('[data-market-reset]')?.click();
      var row=Array.from(shop.querySelectorAll('[data-mkt-row]')).find(function (node) { return node.dataset.target===target; });
      if (row) row.click();
      if (!window.matchMedia('(max-width:1023px)').matches) shop.scrollIntoView({block:'start'});
    } else {
      shop.scrollIntoView({block:'start'});
      shop.querySelector('[data-shop-personagem], [data-shop-search]')?.focus({preventScroll:true});
    }
  });
  if (location.hash==='#balcao-compra') checkout.open=true;
  var links=Array.from(document.querySelectorAll('.market-reference-sidebar nav a'));
  var sections=Array.from(document.querySelectorAll('[data-market-reference-group],[data-market-reference-section]'));
  var ticking=false;
  function markReadingPosition() {
    ticking=false;
    var visible=sections.filter(function (section) { return !section.closest('[hidden]'); });
    var limit=parseFloat(getComputedStyle(document.body).getPropertyValue('--bft-header-height'))+40;
    var reached=visible.filter(function (section) { return section.getBoundingClientRect().top<=limit; });
    var current=reached[reached.length-1] || visible[0];
    links.forEach(function (link) { if (current && link.hash==='#'+current.id) link.setAttribute('aria-current','location'); else link.removeAttribute('aria-current'); });
  }
  function schedulePosition() { if (!ticking) { ticking=true; requestAnimationFrame(markReadingPosition); } }
  window.addEventListener('scroll',schedulePosition,{passive:true});
  window.addEventListener('resize',schedulePosition);
  search.addEventListener('input',schedulePosition);
  document.addEventListener('toggle',schedulePosition,true);
  markReadingPosition();
})();
