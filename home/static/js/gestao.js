(() => {
  const form = document.querySelector('[data-grant-selection]');
  if (form) {
    // Browse via POST so a draft reason never enters the URL or browser history.
    const browse = (url) => {
      form.action = url;
      const action = document.createElement('input');
      action.type = 'hidden';
      action.name = 'action';
      action.value = 'browse';
      form.append(action);
      form.noValidate = true;
      form.requestSubmit();
    };
    document.querySelectorAll('.gestao-pagination a').forEach((link) => {
      link.addEventListener('click', (event) => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button) return;
        event.preventDefault();
        browse(link.href);
      });
    });
    document.querySelector('[data-catalog-filters]')?.addEventListener('submit', (event) => {
      event.preventDefault();
      const url = new URL(location.href);
      url.search = new URLSearchParams(new FormData(event.currentTarget)).toString();
      url.hash = 'results';
      browse(url.href);
    });
  }
  document.querySelector('[data-grant-confirm]')?.addEventListener('submit', (event) => {
    const button = event.submitter;
    // Keep the submitter's action in the POST while preventing repeated clicks.
    if (button?.dataset.submitted) event.preventDefault();
    else if (button) {
      button.dataset.submitted = 'true';
      button.setAttribute('aria-disabled', 'true');
    }
  });
})();
