/* Read-only reading aids. Never inspect editorial fields, submit or save. */
(function(){
  'use strict';
  const readingMinutes = text => Math.max(1,Math.ceil(String(text || '').trim().split(/\s+/).filter(Boolean).length/220));
  if(typeof module !== 'undefined') module.exports = {readingMinutes};
  if(typeof document === 'undefined') return;
  function init(){
    const story = document.querySelector('[data-chronicle-source]');
    if(!story) return;
    if(story.dataset.markdownRendered!=='true'){
      const observer=new MutationObserver(() => {
        if(story.dataset.markdownRendered==='true'){ observer.disconnect(); init(); }
      });
      observer.observe(story,{attributes:true,attributeFilter:['data-markdown-rendered']});
      return;
    }
    const label = document.getElementById('chroniclesReadingTime');
    if(label) label.textContent = story.textContent.trim() ? `Cerca de ${readingMinutes(story.textContent)} min` : 'Conteúdo ainda não informado';
    const toc = document.getElementById('chroniclesToc'), links = document.getElementById('chroniclesTocLinks');
    if(!toc || !links) return;
    const grid = document.querySelector('.chronicles-reading-grid'), layout = grid?.querySelector('.cronica-layout'), aside = grid?.querySelector('.chronicles-reading-aside'), time = label?.closest('.chronicles-reading-time');
    const compact = window.matchMedia('(max-width:1000px)');
    function positionTools(){
      if(!grid || !layout || !aside || !time) return;
      if(compact.matches){ grid.insertBefore(time,layout); grid.insertBefore(toc,layout); }
      else { aside.insertBefore(time,aside.firstChild); aside.insertBefore(toc,time.nextSibling); }
    }
    positionTools();
    compact.addEventListener('change',positionTools);
    Array.from(story.querySelectorAll('h2,h3')).filter(heading => heading.textContent.trim()).forEach((heading,index) => {
      if(!heading.id){ let id = `chronicle-section-${index+1}`; while(document.getElementById(id)) id+='-'; heading.id=id; }
      const link = document.createElement('a');
      link.href = '#'+encodeURIComponent(heading.id); link.textContent = heading.textContent; link.dataset.depth=heading.tagName.substring(1);
      link.addEventListener('click',() => { heading.tabIndex=-1; heading.focus({preventScroll:true}); });
      links.appendChild(link);
    });
    toc.hidden = !links.children.length;
    if(compact.matches) toc.open=false;
  }
  // A deferred script runs while readyState is interactive, before the shared
  // Markdown renderer's DOMContentLoaded listener. Wait for that renderer first.
  if(document.readyState==='complete') init();
  else document.addEventListener('DOMContentLoaded',init,{once:true});
})();
