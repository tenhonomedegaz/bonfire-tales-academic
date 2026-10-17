/* Progressive navigation only. Rules are always visible, including without JS. */
(function () {
  'use strict';
  var page = document.querySelector('.conduct-page');
  if (!page) return;
  var links = Array.from(page.querySelectorAll('[data-conduct-nav]'));
  var mobileIndex = page.querySelector('.conduct-mobile-index');
  function syncLocation() {
    links.forEach(function (link) {
      if (link.hash === location.hash) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  }
  page.addEventListener('click', function (event) {
    var link = event.target.closest('a[href^="#"]');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
    var heading = document.getElementById(link.hash.slice(1));
    if (!heading) return;
    // Keep native hash navigation, shared links and browser history intact.
    if (mobileIndex.contains(link)) mobileIndex.open = false;
    requestAnimationFrame(function () { heading.focus({preventScroll: true}); });
  });
  mobileIndex.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && mobileIndex.open) {
      event.preventDefault();
      mobileIndex.open = false;
      mobileIndex.querySelector('summary').focus();
    }
  });
  window.addEventListener('hashchange', syncLocation);
  window.addEventListener('pageshow', syncLocation);
  syncLocation();
})();
