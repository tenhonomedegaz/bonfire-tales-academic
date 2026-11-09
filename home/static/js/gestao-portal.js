(() => {
  'use strict';
  const toggle = document.querySelector('.gestao-menu-toggle');
  const navigation = document.getElementById('gestao-navigation');
  if (!toggle || !navigation) return;
  const mobile = window.matchMedia('(max-width: 700px)');
  const setOpen = (open) => {
    toggle.setAttribute('aria-expanded', String(open));
    navigation.hidden = !open;
  };
  const syncViewport = () => {
    toggle.hidden = !mobile.matches;
    setOpen(!mobile.matches);
  };
  toggle.addEventListener('click', () => {
    setOpen(toggle.getAttribute('aria-expanded') !== 'true');
  });
  navigation.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && mobile.matches) {
      setOpen(false);
      toggle.focus();
    }
  });
  mobile.addEventListener('change', syncViewport);
  syncViewport();
})();
