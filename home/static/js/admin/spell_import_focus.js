document.addEventListener('DOMContentLoaded', () => {
  const destination = document.getElementById('spell-import-errors')
    || document.getElementById('spell-import-result')
    || document.getElementById('spell-import-preview');
  if (destination) destination.focus();
});
