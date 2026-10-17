/* Reading tools only. Never read editor fields, fetch, submit or save. */
(function(){
 'use strict';
 const readingMinutes=text=>Math.max(1,Math.ceil(String(text||'').trim().split(/\s+/).filter(Boolean).length/220));
 if(typeof module!=='undefined')module.exports={readingMinutes};
 if(typeof document==='undefined')return;
 function init(){
  const article=document.querySelector('[data-jornal-markdown]');if(!article)return;
  const label=document.getElementById('journalReadingTime');
  if(label)label.textContent=article.textContent.trim()?`Cerca de ${readingMinutes(article.textContent)} min`:'Conteúdo ainda não informado';
  const toc=document.getElementById('journalToc'),links=document.getElementById('journalTocLinks');if(!toc||!links)return;
  const grid=document.querySelector('.journal-reading-grid'),layout=grid?.querySelector('.artigo-layout'),aside=grid?.querySelector('.journal-reading-aside'),time=label?.closest('.journal-reading-time');
  const compact=window.matchMedia('(max-width:1100px)');
  function positionTools(){
   if(!grid||!layout||!aside||!time)return;
   if(compact.matches||article.dataset.atlasMode==='true'){grid.insertBefore(time,layout);grid.insertBefore(toc,layout);}
   else{aside.insertBefore(time,aside.firstChild);aside.insertBefore(toc,time.nextSibling);}
  }
  positionTools();compact.addEventListener('change',positionTools);
  const headings=Array.from(article.querySelectorAll('h2,h3')).filter(heading=>heading.textContent.trim());
  headings.forEach((heading,index)=>{
   if(!heading.id){let id=`journal-section-${index+1}`;while(document.getElementById(id))id+='-';heading.id=id;}
   const link=document.createElement('a');link.href='#'+encodeURIComponent(heading.id);link.textContent=heading.textContent;link.dataset.depth=heading.tagName.substring(1);
   link.addEventListener('click',()=>{heading.tabIndex=-1;heading.focus({preventScroll:true});});links.appendChild(link);
  });
  toc.hidden=!headings.length;
  if(article.dataset.atlasMode==='true'||compact.matches)toc.open=false;
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
