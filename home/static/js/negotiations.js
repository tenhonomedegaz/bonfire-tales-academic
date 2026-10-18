(() => {
  const norm = value => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  if (typeof document === 'undefined') return;
  const root = document.querySelector('.nt-page'); if (!root) return;
  const search = root.querySelector('#nt-search'), rarity = root.querySelector('#nt-rarity'), tabs = [...root.querySelectorAll('[data-nt-area]')], entries = [...root.querySelectorAll('.nt-item')], panels = [...root.querySelectorAll('.nt-offer')];
  const count = root.querySelector('#nt-count'), label = root.querySelector('#nt-count-label'), listEmpty = root.querySelector('#nt-list-empty'), readerEmpty = root.querySelector('#nt-reader-empty'), clear = root.querySelector('.nt-clear'), announcement = root.querySelector('#nt-announcement'), reader = root.querySelector('#nt-reader');
  const params = () => new URL(location.href).searchParams;
  let area = params().get('area') || 'venda', selected = params().get('anuncio') || '', query = params().get('q') || '', selectedRarity = params().get('raridade') || '';
  [...new Set(entries.map(entry => entry.dataset.rarity).filter(Boolean))].sort().forEach(value => rarity.add(new Option(value, value)));
  search.value = query; rarity.value = selectedRarity;
  const sync = push => { const url = new URL(location.href); url.searchParams.set('area', area); selected ? url.searchParams.set('anuncio', selected) : url.searchParams.delete('anuncio'); query ? url.searchParams.set('q', query) : url.searchParams.delete('q'); selectedRarity ? url.searchParams.set('raridade', selectedRarity) : url.searchParams.delete('raridade'); url.searchParams.delete('m'); history[push ? 'pushState' : 'replaceState'](null, '', url.pathname + url.search); };
  const refresh = requested => { if (!tabs.some(tab => tab.dataset.ntArea === area)) area = 'venda'; const visible = entries.filter(entry => { const yes = entry.dataset.area === area && norm(entry.dataset.search).includes(norm(query)) && (!selectedRarity || entry.dataset.rarity === selectedRarity); entry.hidden = !yes; return yes; }); selected = visible.some(entry => entry.dataset.key === requested) ? requested : (visible[0] && visible[0].dataset.key) || ''; panels.forEach(panel => { panel.hidden = panel.id !== `nt-offer-${selected}`; }); if (selected) reader.setAttribute('aria-labelledby', 'nt-name-' + selected); else reader.removeAttribute('aria-labelledby'); entries.forEach(entry => entry.setAttribute('aria-current', entry.dataset.key === selected ? 'true' : 'false')); tabs.forEach(tab => { if (tab.dataset.ntArea === area) tab.setAttribute('aria-current', 'page'); else tab.removeAttribute('aria-current'); }); count.textContent = visible.length; label.textContent = visible.length === 1 ? 'anúncio encontrado' : 'anúncios encontrados'; listEmpty.hidden = visible.length > 0; readerEmpty.hidden = visible.length > 0; root.querySelector('#nt-empty-scope').textContent = area === 'meus' ? 'Meus anúncios' : 'Vitrine da comunidade'; clear.hidden = !query && !selectedRarity; announcement.textContent = `${visible.length} ${label.textContent}.`; };
  root.querySelector('.nt-filter').addEventListener('submit', event => { event.preventDefault(); query = search.value.trim().slice(0, 160); selectedRarity = rarity.value; refresh(''); sync(true); });
  search.addEventListener('input', () => { query = search.value.trim().slice(0, 160); refresh(''); sync(false); }); rarity.addEventListener('change', () => { selectedRarity = rarity.value; refresh(''); sync(false); });
  tabs.forEach(tab => tab.addEventListener('click', () => { area = tab.dataset.ntArea; refresh(''); sync(true); })); entries.forEach(entry => entry.addEventListener('click', () => { selected = entry.dataset.key; refresh(selected); sync(true); reader.focus({ preventScroll: true }); })); clear.addEventListener('click', () => { search.value = ''; rarity.value = ''; query = ''; selectedRarity = ''; refresh(''); sync(true); search.focus({ preventScroll: true }); });
  addEventListener('popstate', () => { area = params().get('area') || 'venda'; query = params().get('q') || ''; selectedRarity = params().get('raridade') || ''; search.value = query; rarity.value = selectedRarity; refresh(params().get('anuncio') || ''); }); refresh(selected);
  const review = root.querySelector('#nt-review');
  if (!review || typeof review.showModal !== 'function') return;
  const proceed = review.querySelector('[data-nt-proceed]');
  let pending = null;
  let opener = null;
  let approved = null;
  for (const form of root.querySelectorAll('form[data-nt-review]')) {
    form.addEventListener('submit', event => {
      if (approved === form) { approved = null; return; }
      event.preventDefault();
      if (!form.reportValidity()) return;
      pending = form;
      opener = event.submitter || form.querySelector('[type="submit"]');
      const buying = form.dataset.ntReview === 'buy';
      const character = buying ? form.querySelector('[name="comprador"]') : null;
      const selectedCharacter = character?.selectedOptions[0];
      review.querySelector('#nt-review-title').textContent = buying ? 'Revisar compra' : 'Revisar cancelamento';
      review.querySelector('[data-nt-product]').textContent = form.dataset.ntProduct || '';
      review.querySelector('[data-nt-price-row]').hidden = !buying;
      review.querySelector('[data-nt-price]').textContent = buying ? form.dataset.ntPrice || '' : '';
      review.querySelector('[data-nt-character]').textContent = buying ? selectedCharacter?.textContent || '' : form.closest('.nt-offer').querySelector('.nt-vendor strong').textContent;
      review.querySelector('[data-nt-note]').textContent = buying
        ? 'O valor será debitado do personagem escolhido e o item irá para a mochila dele. O servidor confere saldo e disponibilidade ao confirmar.'
        : 'O item anunciado voltará para a mochila do personagem vendedor.';
      proceed.textContent = buying ? 'Confirmar compra' : 'Cancelar anúncio';
      review.showModal();
    });
  }
  for (const close of review.querySelectorAll('[data-nt-close]')) close.addEventListener('click', () => review.close());
  review.addEventListener('close', () => { pending = null; opener?.focus(); });
  proceed.addEventListener('click', () => {
    const form = pending;
    if (!form || !form.reportValidity()) return;
    pending = null;
    review.close();
    approved = form;
    form.requestSubmit();
  });
})();
