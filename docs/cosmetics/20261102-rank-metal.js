(() => {
 'use strict';
 const staticPath=value=>value.replace(/^\/static\//,'../../home/static/');
 const local=pack=>JSON.parse(JSON.stringify(pack).replaceAll('/static/','../../home/static/'));
 const grid=document.getElementById('ranks');
 for(const row of window.BonfireRankMetalPreview.cosmetics){
  const section=document.createElement('section');
  section.className='rank-preview '+row.css_class;
  section.dataset.rank=row.slug;
  section.innerHTML='<h2 class="rank-label"><img src="'+staticPath(row.icon)+'" width="40" height="40" alt="">'+row.nome+'</h2><div class="public-profile-card"><div class="banner"></div><div class="identity"><div class="rank-avatar hero-avatar"><img src="../../home/static/brand/human.webp" alt="Retrato" width="80" height="80"></div><div><h3 class="name">Aventureiro de Cinéria</h3><p class="handle">@aventureiro</p></div></div><div class="frames"><div class="frame-sample"><div class="rank-avatar open-avatar"><img src="../../home/static/brand/dwarf.webp" alt="Retrato" width="80" height="80"></div><small>Aberta</small></div><div class="frame-sample"><div class="rank-avatar closed-avatar" tabindex="0"><img src="../../home/static/brand/human.webp" alt="Retrato" width="80" height="80"></div><small>Fechada</small></div></div></div><section class="public-profile-section"><h3>Conquistas</h3><p>'+row.nome+'<br>Conquista permanente</p></section><section class="ficha-card rank-sheet"><h3>Guardião de Cinéria</h3><div class="stats"><div><span>Força</span><strong>18</strong></div><div><span>Destreza</span><strong>14</strong></div><div><span>Constituição</span><strong>16</strong></div></div></section>';
  grid.appendChild(section);
  section.querySelectorAll('.rank-avatar').forEach(avatar=>avatar.classList.add('public-profile-avatar'));
  for(const selector of ['.hero-avatar','.open-avatar'])CosmeticRenderer.render(section.querySelector(selector),'avatar',[local(row.open)]);
  CosmeticRenderer.render(section.querySelector('.closed-avatar'),'avatar',[local(row.closed)]);
 }
 document.getElementById('motion').addEventListener('click',event=>{
  const enabled=event.currentTarget.getAttribute('aria-pressed')!=='true';
  event.currentTarget.setAttribute('aria-pressed',String(enabled));
  document.documentElement.classList.toggle('preview-paused',!enabled);
 });
})();
