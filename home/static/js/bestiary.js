/* Switch already-rendered statblocks; never changes creature data or the rule engine. */
(() => {
  const list = document.getElementById('bz-list');
  const sheet = document.getElementById('bz-sheet');
  if (!list || !sheet) return;
  const links = Array.from(list.querySelectorAll('.bz-item'));
  const panels = Array.from(sheet.querySelectorAll('.monster-panel'));
  const activeInput = document.getElementById('bz-active');
  const announcement = document.getElementById('bz-announcement');
  let activeView = 'sheet';
  function setView(panel, mode) {
    panel.querySelectorAll('[data-creature-content]').forEach(content => {
      content.hidden = content.dataset.creatureContent !== mode;
    });
    panel.querySelectorAll('[data-creature-view]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.creatureView === mode));
    });
  }
  panels.forEach(panel => {
    const controls = panel.querySelector('.be-view-switch');
    if (controls) controls.hidden = false;
    panel.querySelectorAll('[data-creature-view]').forEach(button => button.addEventListener('click', () => {
      activeView = button.dataset.creatureView;
      setView(panel, activeView);
    }));
  });
  function show(id, updateUrl = false) {
    const panel = panels.find(item => item.id === id);
    const link = links.find(item => item.dataset.target === id);
    if (!panel || !link) return false;
    setView(panel, activeView);
    panels.forEach(item => item.classList.toggle('hidden', item !== panel));
    links.forEach(item => {
      item.classList.toggle('is-active', item === link);
      if (item === link) item.setAttribute('aria-current', 'true');
      else item.removeAttribute('aria-current');
    });
    if (activeInput) activeInput.value = id.replace(/^monster-/, '');
    if (announcement) announcement.textContent = 'Ficha de ' + panel.querySelector('.monster-title').textContent.trim() + ' selecionada.';
    if (updateUrl) history.replaceState(null, '', link.href);
    return true;
  }
  links.forEach((link, index) => {
    link.addEventListener('click', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
      if (!show(link.dataset.target, true)) return;
      event.preventDefault();
      if (window.matchMedia('(max-width: 760px)').matches) {
        sheet.focus({preventScroll:true});
        sheet.scrollIntoView({block:'start', behavior:'auto'});
      }
    });
    link.addEventListener('keydown', event => {
      const next = event.key === 'ArrowDown' ? Math.min(index + 1, links.length - 1) :
                   event.key === 'ArrowUp' ? Math.max(index - 1, 0) :
                   event.key === 'Home' ? 0 : event.key === 'End' ? links.length - 1 : null;
      if (next === null) return;
      event.preventDefault();
      links[next].focus();
      show(links[next].dataset.target, true);
    });
  });
  function fromLocation() {
    const match = location.hash.match(/^#(monster-\d+)(?:-|$)/);
    if (match) {
      activeView = location.hash.endsWith('-art') ? 'art' : 'sheet';
      show(match[1]);
    }
    const target = location.hash && document.getElementById(location.hash.slice(1));
    if (target instanceof HTMLDetailsElement) target.open = true;
  }
  fromLocation();
  window.addEventListener('hashchange', fromLocation);
  window.addEventListener('popstate', fromLocation);
  sheet.addEventListener('click', event => {
    const anchor = event.target.closest('.be-sheet-index a');
    if (!anchor) return;
    const target = document.getElementById(anchor.hash.slice(1));
    if (target instanceof HTMLDetailsElement) target.open = true;
  });
})();
