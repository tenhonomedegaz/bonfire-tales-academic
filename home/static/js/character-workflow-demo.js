/* Loaded exclusively by the isolated design adapter, never a production template. */
(() => {
  if(!document.querySelector('.cw-demo-notice'))return;
  function blocked(event){event.preventDefault();event.stopImmediatePropagation();const box=document.querySelector('[data-workflow-demo-status]');if(box)box.textContent='PrÃ©via somente de leitura: nenhuma alteraÃ§Ã£o foi salva.';}
  document.addEventListener('submit',event=>{if(event.target.closest('main')&&event.target.method.toLowerCase()==='post')blocked(event);},true);
  document.addEventListener('click',event=>{if(event.target.closest('[data-sn-confirm]'))blocked(event);},true);
  const confirm=document.querySelector('[data-sn-confirm]');
  if(confirm){const lock=()=>{if(!confirm.disabled)confirm.disabled=true;};lock();new MutationObserver(lock).observe(confirm,{attributes:true,attributeFilter:['disabled']});}
})();

