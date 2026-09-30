/* figg. — a tiny, framework-free, offline-friendly creative studio. */
(() => {
  'use strict';
  const items = [
    ['01','classic','The original','core'],['02','wink','A little wink','core'],['03','sitting','Take five','core'],['04','tall','Standing tall','core'],
    ['05','joy','Pure joy','core'],['06','side','From the side','core'],['07','wave','Hi there','core'],['08','sleepy','Slow mornings','core'],
    ['09','sparkle','Magic moment','expressions'],['10','crown','Little royalty','occasions'],['11','curious','Curious figg','expressions'],['12','scarf','Wrapped up','occasions'],
    ['13','heart','With love','occasions'],['14','headphones','In my zone','accessories'],['15','cheeky','A cheeky hello','expressions'],['16','shades','Incognito','accessories'],
    ['17','tilt','A new angle','core'],['18','nap','Extra cozy','expressions'],['19','jump','Can’t contain it','expressions'],['20','quiet','Just here','core'],
    ['21','bashful','Blushing','expressions'],['22','sprout','Growing on you','accessories'],['23','cap','Out and about','accessories'],['24','star','You’re a star','occasions'],
    ['25','back','See you soon','core'],['26','bow','Dressed up','accessories'],['27','cheer','Big day','expressions'],['28','hoodie','Comfy club','accessories'],
    ['29','glasses','A bright idea','accessories'],['30','belly','Grounded','expressions'],['31','love','Little crush','occasions'],['32','cosmic','Night mode','occasions']
  ].map(([id,slug,name,category]) => ({id,slug,name,category,svg:`assets/mascots/svg/${id}-${slug}.svg`,png:`assets/mascots/png/${id}-${slug}.png`}));
  let active = items[0]; let filter = 'all';
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const featured = ['01','02','05','08','13','19']; const minis = ['10','12','14','22','23','24','26','28'];
  const nice = s => s.replaceAll('’',"'");
  const escapeHtml = s => String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const makeOption = i => `<button class="variant-chip ${active.id === i.id ? 'active':''}" data-id="${i.id}" type="button" aria-pressed="${active.id===i.id}">${escapeHtml(i.name)}<span>${i.id} / 32</span></button>`;
  function renderFeatured(){
    $('#variant-buttons').innerHTML = featured.map(id=>makeOption(items.find(i=>i.id===id))).join('');
    $('#mini-variant-strip').innerHTML = minis.map(id=>{const i=items.find(x=>x.id===id);return `<button type="button" class="mini-variant" data-id="${i.id}" aria-label="Choose ${escapeHtml(i.name)}"><img src="${i.svg}" alt="" loading="lazy"></button>`}).join('');
    $('#variant-select').innerHTML = items.map(i=>`<option value="${i.id}">${escapeHtml(i.name)}</option>`).join('');
    $('#variant-select').value=active.id;
  }
  function renderGallery(){
    const list=items.filter(i=>filter==='all'||i.category===filter);
    $('#mascot-grid').innerHTML=list.map(i=>`<button class="mascot-card ${active.id===i.id?'selected':''}" data-id="${i.id}" type="button" aria-label="Select ${escapeHtml(i.name)} mascot" aria-pressed="${active.id===i.id}">
      <span class="mascot-card-visual"><span class="mascot-card-no">${i.id} / 32</span><span class="mascot-card-arrow" aria-hidden="true">↗</span><img src="${i.svg}" loading="lazy" alt="${escapeHtml(i.name)} purple figg mascot"/></span>
      <span class="mascot-card-meta"><strong>${escapeHtml(i.name)}</strong><span>SVG ↗</span></span></button>`).join('');
    $('#library-count').textContent=`SHOWING ${list.length} OF 32`;
  }
  let toastTimer;
  function toast(msg){let t=$('#toast');t.textContent=msg;t.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.remove('show'),2800)}
  function choose(id, scroll=false){
    active=items.find(i=>i.id===id)||items[0];
    $('#studio-figure').src=active.svg; $('#studio-figure').alt=`Preview of ${nice(active.name)} figg mascot`;
    $('#preview-name').textContent=active.name+'.'; $('#preview-index').textContent=`${active.id} / 32 ↗`;
    $('#variant-number').textContent=`${active.id} / 32`;
    $('#variant-select').value=active.id;
    $('#download-svg').href=active.svg;$('#download-svg').download=`figg-${active.slug}.svg`;
    $('#download-png').href=active.png;$('#download-png').download=`figg-${active.slug}.png`;
    $$('.variant-chip').forEach(b=>{let selected=b.dataset.id===id;b.classList.toggle('active',selected);b.setAttribute('aria-pressed',String(selected))});
    $$('.mascot-card').forEach(b=>{let selected=b.dataset.id===id;b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(selected))});
    if(scroll){$('#studio').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});toast(`${active.name} is now in your studio.`)}
  }
  function changeFilter(next){filter=next;$$('.filter').forEach(b=>{let yes=b.dataset.filter===filter;b.classList.toggle('active',yes);b.setAttribute('aria-pressed',String(yes))});renderGallery()}
  function scene(next){let elem=$('#studio-preview');elem.className='studio-preview theme-'+next;$$('.scene-button').forEach(b=>{let yes=b.dataset.scene===next;b.classList.toggle('selected',yes);b.setAttribute('aria-pressed',String(yes))})}
  async function copyText(s){
    try{if(navigator.clipboard&&window.isSecureContext){await navigator.clipboard.writeText(s);return true}}
    catch(e){}
    try{let n=document.createElement('textarea');n.value=s;n.style.cssText='position:fixed;opacity:0;top:0';document.body.append(n);n.select();let ok=document.execCommand('copy');n.remove();return ok}catch(e){return false}
  }
  renderFeatured();renderGallery();
  $('#variant-buttons').addEventListener('click',e=>{let b=e.target.closest('[data-id]');if(b)choose(b.dataset.id)});
  $('#mini-variant-strip').addEventListener('click',e=>{let b=e.target.closest('[data-id]');if(b)choose(b.dataset.id)});
  $('#variant-select').addEventListener('change',e=>choose(e.target.value));
  $('#mascot-grid').addEventListener('click',e=>{let b=e.target.closest('[data-id]');if(b)choose(b.dataset.id,true)});
  $('#library-filters').addEventListener('click',e=>{let b=e.target.closest('[data-filter]');if(b)changeFilter(b.dataset.filter)});
  $$('.scene-button').forEach(b=>b.addEventListener('click',()=>scene(b.dataset.scene)));
  $$('.swatch-card').forEach(b=>b.addEventListener('click',async()=>{let success=await copyText(b.dataset.copy);toast(success?`${b.dataset.copy} copied. Nice choice.`:`Hex color: ${b.dataset.copy}`)}));
  // Smooth responsive mobile navigation, focusable and fully dismissible.
  const menu=$('#menu-toggle'),mobile=$('#mobile-nav');
  function closeMenu(){mobile.hidden=true;menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','Open navigation')}
  menu.addEventListener('click',()=>{let open=mobile.hidden;mobile.hidden=!open;menu.setAttribute('aria-expanded',String(open));menu.setAttribute('aria-label',open?'Close navigation':'Open navigation')});
  mobile.querySelectorAll('a').forEach(a=>a.addEventListener('click',closeMenu));
  window.addEventListener('keydown',e=>{if(e.key==='Escape')closeMenu()});
  window.addEventListener('resize',()=>{if(innerWidth>1000)closeMenu()});
  // Lightweight guided scroll indicator.
  let scrollPending=false;
  function onScroll(){if(scrollPending)return;scrollPending=true;requestAnimationFrame(()=>{let max=document.documentElement.scrollHeight-innerHeight;$('#progress').style.width=`${max>0?100*scrollY/max:0}%`;scrollPending=false})}
  window.addEventListener('scroll',onScroll,{passive:true});onScroll();
  // Useful console affordance for anyone continuing this brand project.
  window.FIGG_STUDIO={version:'1.0.0',variants:items,select:choose,filter:changeFilter,scene};
})();
