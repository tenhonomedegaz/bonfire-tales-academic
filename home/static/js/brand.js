/* Progressive enhancement: navigation and FAQ also work without JavaScript. */
document.addEventListener('DOMContentLoaded', () => {
  const disclosures = [...document.querySelectorAll('.bft-disclosure')];
  const mobile = document.querySelector('.bft-mobile-menu');
  function closeMenus(except = null) {
    disclosures.forEach(menu => { if (menu !== except) menu.open = false; });
  }
  disclosures.forEach(menu => {
    menu.addEventListener('toggle', () => {
      if (menu.open) closeMenus(menu);
      if (menu === mobile) document.body.style.overflow = menu.open ? 'hidden' : '';
    });
    menu.addEventListener('click', event => {
      if (event.target.closest('a')) closeMenus();
    });
  });
  document.addEventListener('click', event => {
    disclosures.forEach(menu => { if (!menu.contains(event.target)) menu.open = false; });
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const open = disclosures.find(menu => menu.open);
    if (open) { closeMenus(); open.querySelector('summary').focus(); }
  });
  const mobileBreakpoint = window.matchMedia('(max-width:1099px)');
  mobileBreakpoint.addEventListener('change', () => closeMenus());

  document.querySelectorAll('[data-bft-tabs]').forEach(group => {
    const list = group.querySelector('.bft-tabs');
    const tabs = [...list.querySelectorAll('button')];
    const panels = [...group.querySelectorAll('.bft-reason-panel')];
    function select(index, focus = false) {
      tabs.forEach((tab, i) => {
        tab.setAttribute('aria-selected', String(i === index));
        tab.tabIndex = i === index ? 0 : -1;
        panels[i].hidden = i !== index;
      });
      if (focus) tabs[index].focus();
    }
    list.hidden = false;
    list.setAttribute('role', 'tablist');
    tabs.forEach((tab, i) => {
      tab.setAttribute('role', 'tab');
      panels[i].setAttribute('role', 'tabpanel');
      panels[i].setAttribute('aria-labelledby', tab.id);
      panels[i].tabIndex = 0;
      tab.addEventListener('click', () => select(i));
      tab.addEventListener('keydown', event => {
        const direction = {ArrowRight:1, ArrowLeft:-1}[event.key];
        if (direction || event.key === 'Home' || event.key === 'End') {
          event.preventDefault();
          select(event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (i + direction + tabs.length) % tabs.length, true);
        }
      });
    });
    select(0);
  });
});
