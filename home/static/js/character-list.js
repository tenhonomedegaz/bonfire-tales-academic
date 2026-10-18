/* Client-only finding aid; does not intercept any character management forms. */
(() => {
  const root=document.querySelector('.cw-list-page');if(!root)return;
  const controls=root.querySelector('[data-cw-controls]'),search=root.querySelector('#cw-search'),group=root.querySelector('#cw-group');
  const cards=[...root.querySelectorAll('[data-cw-card]')],groups=[...root.querySelectorAll('[data-cw-group]')];
  if(!controls||!search||!group)return;
  const norm=v=>String(v||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  function filter(){let count=0;cards.forEach(card=>{const visible=(!group.value||group.value===card.dataset.cwKind)&&norm(card.dataset.cwSearch).includes(norm(search.value.trim()));card.hidden=!visible;if(visible)count++;});groups.forEach(section=>section.hidden=!!(search.value||group.value)&&![...section.querySelectorAll('[data-cw-card]')].some(c=>!c.hidden));root.querySelector('[data-cw-count]').textContent=`${count} ficha${count===1?'':'s'} encontrada${count===1?'':'s'}`;root.querySelector('[data-cw-empty]').hidden=count>0||(!search.value&&!group.value);}
  controls.hidden=false;search.addEventListener('input',filter);group.addEventListener('change',filter);root.querySelector('[data-cw-clear]').addEventListener('click',()=>{search.value='';group.value='';filter();search.focus();});filter();
  const staffControls=root.querySelector('[data-cw-staff-controls]');
  if(!staffControls)return;
  const staffSearch=staffControls.querySelector('#cw-staff-search'),staffGroup=staffControls.querySelector('#cw-staff-group');
  const staffCards=[...root.querySelectorAll('[data-cw-staff-card]')];
  function filterStaff(){
    let count=0;
    staffCards.forEach(card=>{
      const visible=(!staffGroup.value||staffGroup.value===card.dataset.cwStaffKind)&&norm(card.dataset.cwStaffSearch).includes(norm(staffSearch.value.trim()));
      card.hidden=!visible;
      if(visible)count++;
    });
    staffControls.querySelector('[data-cw-staff-count]').textContent=`${count} ficha${count===1?'':'s'} de outras contas encontrada${count===1?'':'s'}`;
    root.querySelector('[data-cw-staff-empty]').hidden=count>0||(!staffSearch.value.trim()&&!staffGroup.value);
  }
  staffControls.hidden=false;
  staffSearch.addEventListener('input',filterStaff);
  staffGroup.addEventListener('change',filterStaff);
  staffControls.querySelector('[data-cw-staff-clear]').addEventListener('click',()=>{staffSearch.value='';staffGroup.value='';filterStaff();staffSearch.focus();});
  filterStaff();
})();
