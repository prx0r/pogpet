/* OddHobb saved scene editor. Uses the host's existing session and auth. */
(function () {
  'use strict';
  function el(tag, text, cls) {
    var n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  }
  function button(text, action, cls) {
    var b = el('button', text, cls || 'oc-button'); b.type = 'button';
    b.addEventListener('click', action); return b;
  }
  function label(text, input) {
    var l = el('label', undefined, 'oc-field'); l.append(el('span', text), input); return l;
  }
  function input(max, multiline) {
    var n = el(multiline ? 'textarea' : 'input'); n.maxLength = max;
    if (!multiline) n.type = 'text'; return n;
  }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  window.OddHobbCards = function (host) {
    var state = { photos: [], selected: [], slots: {}, templates: [], formats: {}, fonts: {}, template: 'portrait', format: '5x7', headlineFont: 'fraunces', insideFont: 'inter', id: '', revision: 0, cropTarget: '', dirty: 0, chain: Promise.resolve(), ready: null };
    var cardPrice='£7.99';
    var library = el('div', undefined, 'oc-library');
    var panel = document.querySelector('#panel-cards .panel__inner');
    var studio = document.querySelector('#panel-studio .panel__inner');
    var status = el('p', '', 'oc-status'); status.setAttribute('role', 'status');status.setAttribute('aria-live','polite');
    var uploads = el('div', undefined, 'oc-uploads');
    var grid = el('div', undefined, 'oc-photos');
    var selectedLine = el('p', '', 'oc-status');
    var file = el('input');file.type='file';file.accept='image/jpeg,image/png,image/webp';file.multiple=true;file.hidden=true;
    var toolbar=el('div',undefined,'oc-toolbar');
    toolbar.append(button('Upload photos',function(){file.click();}),button('Make a greeting card',function(){host.tab('cards');open();}),button('Refresh',refresh));
    library.append(el('h3','Your photo library'),el('p','Upload Dad, Mum, the kids or your pets. Select photos to use in your card.'),toolbar,file,uploads,selectedLine,grid);
    // Studio owns uploads. This library is a photo picker inside the card editor.
    toolbar.replaceChildren();
    library.replaceChildren(el('h3','Photos for this card'),selectedLine,grid);
    // Replace the two disconnected legacy card forms and their ornament order buttons.
    if(panel) panel.replaceChildren();
    var header=el('div',undefined,'store-head');header.append(el('h2','Greeting cards'),el('p','Give them a starring moment. Save the card, then bring it to life.'));
    var cardsLibrary=el('div',undefined,'oc-library');
    cardsLibrary.append(button('Manage photos in Studio',function(){host.tab('studio');}));
    var choices=el('div',undefined,'oc-templates');var sceneNote=el('p','','oc-status');var quality=el('p','','oc-status');
    var saved=el('select');saved.setAttribute('aria-label','Saved greeting cards');
    saved.append(new Option('New card',''));
    var form=el('div',undefined,'oc-form');
    var headline=input(160),recipient=input(60),sender=input(100),inside=input(1200,true),format=el('select');
    var headlineFont=el('select'),insideFont=el('select');
    headlineFont.setAttribute('aria-label','Headline font');insideFont.setAttribute('aria-label','Inside message font');
    headlineFont.addEventListener('change',function(){state.headlineFont=headlineFont.value;changed();});
    insideFont.addEventListener('change',function(){state.insideFont=insideFont.value;changed();});
    var inputs={headline:headline,recipient:recipient,sender:sender,inside_message:inside};
    var price=el('p','','oc-price');
    form.append(label('Saved designs',saved),label('Front headline',headline),label('Headline font',headlineFont),label('Starring',recipient),label('From',sender),label('Inside message',inside),label('Inside font',insideFont),label('Card format',format),price);
    var crop=el('section',undefined,'oc-crop');
    var photoSelect=el('select');photoSelect.setAttribute('aria-label','Photo to crop');
    var canvas=el('canvas');canvas.width=640;canvas.height=480;canvas.setAttribute('aria-label','Drag a box around the subject. Keyboard users can adjust the crop coordinates below.');
    var coords=el('div',undefined,'oc-coords');
    var cropInputs=['Left','Top','Width','Height'].map(function(name,i){var n=el('input');n.type='number';n.min='0';n.max='1';n.step='0.01';n.setAttribute('aria-label','Crop '+name);n.addEventListener('change',function(){var s=slot(state.cropTarget);s.crop[i]=Number(n.value);s.cutout='';drawCrop();changed();});coords.append(label(name,n));return n;});
    var fx=el('input'),fy=el('input');[fx,fy].forEach(function(n){n.type='range';n.min='0';n.max='1';n.step='0.01';});
    fx.addEventListener('input',function(){slot(state.cropTarget).focus[0]=Number(fx.value);changed();});
    fy.addEventListener('input',function(){slot(state.cropTarget).focus[1]=Number(fy.value);changed();});
    var cut=button('Remove background',removeBackground);
    crop.append(el('h3','Pick the subject'),el('p','For group photos, drag a box around Dad first. Check the cutout before using it.'),photoSelect,canvas,coords,label('Horizontal framing',fx),label('Vertical framing',fy),cut,button('Use original photo',function(){slot(state.cropTarget).cutout='';drawCrop();changed();}),button('Reset crop',function(){slot(state.cropTarget).crop=[0,0,1,1];slot(state.cropTarget).cutout='';drawCrop();changed();}));
    var cropResult=el('img');cropResult.hidden=true;cropResult.alt='Background-removed subject';crop.append(cropResult);
    var preview=el('img');preview.alt='Your saved card front';preview.hidden=true;
    var insidePreview=el('img');insidePreview.alt='Your saved card inside — click to edit the message';insidePreview.hidden=true;
    insidePreview.style.cursor='pointer';insidePreview.title='Click to edit the inside message';
    insidePreview.addEventListener('click',function(){inside.focus();inside.scrollIntoView({block:'center'});});
    var spreadWrap=el('div',undefined,'oc-spread');spreadWrap.hidden=true;
    var triptychFig=el('figure',undefined,'oc-face oc-triptych');
    var triptychImg=el('img');triptychImg.alt='Card preview — front, inside, back';
    triptychImg.loading='lazy';triptychFig.append(el('figcaption','Preview — front · inside · back'),triptychImg);
    spreadWrap.append(triptychFig);
    var spreadImgs={},spreadParts=[['front','Front'],['inside_left','Inside left'],['inside_right','Inside right'],['back','Back']];
    spreadParts.forEach(function(p){var fig=el('figure',undefined,'oc-face');var im=el('img');im.alt='Card '+p[1];im.loading='lazy';fig.append(el('figcaption',p[1]),im);spreadWrap.append(fig);spreadImgs[p[0]]=im;});
    var spreadBtn=button('Show all faces',function(){showSpread().catch(error);});
    var flipBtn=button('Front ↔ back',function(){var on=spreadWrap.classList.toggle('oc-flipped');spreadParts.forEach(function(p){if(p[0]==='inside_left'||p[0]==='inside_right')spreadImgs[p[0]].parentNode.hidden=on;});});
    var empty=el('p','Choose photos in Studio, or select the typography template to start.','oc-empty');
    var previews=el('div',undefined,'oc-previews');previews.append(empty,preview,insidePreview,spreadBtn,flipBtn,spreadWrap);
    var video=el('video');video.controls=true;video.playsInline=true;video.hidden=true;video.preload='none';
    var downloads=el('div',undefined,'oc-downloads');
    var save=button('Save & preview',function(){savePreview().catch(error);});
    var exportBtn=button('Download print PDF',function(){produce('export').catch(error);});
    var motionBtn=button('Bring this card to life',function(){produce('motion').catch(error);});
    var orderBtn=button('Buy this card · '+cardPrice,buy);
    var actions=el('div',undefined,'oc-toolbar');actions.append(save,exportBtn,motionBtn,button('View matching video',async function(){try{var x=await savePreview();await videos(x.id);var item=sceneGrid.querySelector('[data-scene-id="'+x.id+'"]');if(item&&item.scrollIntoView)item.scrollIntoView({block:'start'});}catch(e){error(e);}}),orderBtn,button('New card',newCard));
    // Editor is tinkerer tools: collapsed by default, gallery + scenes lead.
    var tinkerer=el('details',undefined,'oc-tinkerer');
    var tinkererSummary=el('summary','Tinkerer tools (forms)');
    tinkerer.append(tinkererSummary,header,cardsLibrary,library,choices,sceneNote,form,crop,previews,quality,status,actions,video,downloads,el('p','Fixed '+cardPrice+' per card (5×7, envelope included). Buy takes you to Shopify checkout; Prodigi prints after payment.','panel__fine'));
    if(panel) panel.append(tinkerer);
    var timer,image,canvasRect,drag;
    function error(e){status.textContent=e.message||String(e);}
    function slot(pid){return state.slots[pid]||(state.slots[pid]={photo_id:pid,crop:[0,0,1,1],focus:[.5,.5],cutout:''});}
    function tpl(){return state.templates.find(function(t){return t.id===state.template;});}
    function chosen(){var t=tpl();return t?state.selected.slice(0,t.max_photos):[];}
    function spec(){var s={template:state.template,format:state.format,photos:chosen().map(function(pid){return JSON.parse(JSON.stringify(slot(pid)));}),headline_font:state.headlineFont,inside:{right:{message:inputs.inside_message.value,font:state.insideFont},left:{mode:'blank'}}};Object.keys(inputs).forEach(function(k){s[k]=inputs[k].value;});return s;}
    function paintChoices(){sceneNote.textContent=tpl()?'Matching clip: '+tpl().motion+'.':'';choices.replaceChildren();state.templates.forEach(function(t){choices.append(button(t.label,function(){state.template=t.id;headline.value=t.headline;paintChoices();paintCropChoices();changed();},'oc-button'+(t.id===state.template?' selected':'')));});}
    function refresh(){return host.ready().then(function(){return host.get('/cards/photos');}).then(function(d){state.photos=d.photos;paintPhotos();paintCropChoices();}).catch(error);}
    function paintPhotos(){grid.replaceChildren();state.photos.filter(function(p){var ctx=window.OddHobbStudioContext;return state.id||!ctx||!ctx.subject||ctx.photos.some(function(x){return x.id===p.id;});}).forEach(function(p){var b=button('',function(){var i=state.selected.indexOf(p.id);if(i>=0)state.selected.splice(i,1);else if(state.selected.length<5)state.selected.push(p.id);else{status.textContent='Select up to five photos.';return;}paintPhotos();paintCropChoices();changed();},'oc-photo'+(state.selected.includes(p.id)?' selected':''));b.setAttribute('aria-pressed',String(state.selected.includes(p.id)));var im=el('img');im.src=host.asset(p.url);im.alt=p.orig_name||'Uploaded photo';im.loading='lazy';b.append(im,el('span',p.person||p.orig_name||'Photo'));grid.append(b);});selectedLine.textContent=state.selected.length+' photos selected. The first selected photo is the star in single-photo scenes.';}
    function paintCropChoices(){photoSelect.replaceChildren();chosen().forEach(function(pid){var p=state.photos.find(function(x){return x.id===pid;});photoSelect.append(new Option(p?p.orig_name:pid,pid));});crop.hidden=!chosen().length;state.cropTarget=chosen().includes(state.cropTarget)?state.cropTarget:chosen()[0]||'';photoSelect.value=state.cropTarget;drawCrop();}
    photoSelect.addEventListener('change',function(){state.cropTarget=photoSelect.value;drawCrop();});
    function drawCrop(){var pid=state.cropTarget,p=state.photos.find(function(x){return x.id===pid;});if(!p)return;var s=slot(pid);cropInputs.forEach(function(n,i){n.value=s.crop[i];});fx.value=s.focus[0];fy.value=s.focus[1];cropResult.hidden=!s.cutout;if(s.cutout)cropResult.src=host.asset('/cards/cutouts/'+s.cutout+'/image');image=new Image();image.onload=function(){if(state.cropTarget!==pid)return;var ratio=Math.min(canvas.width/image.width,canvas.height/image.height);canvasRect={x:(canvas.width-image.width*ratio)/2,y:(canvas.height-image.height*ratio)/2,w:image.width*ratio,h:image.height*ratio};paintCanvas();};image.onerror=function(){status.textContent='Could not load that photo. Refresh and try again.';};image.src=host.asset(p.url);}
    function paintCanvas(){if(!image||!canvasRect||!state.cropTarget)return;var c=canvas.getContext('2d'),r=canvasRect,b=slot(state.cropTarget).crop;c.fillStyle='#e8e5df';c.fillRect(0,0,canvas.width,canvas.height);c.drawImage(image,r.x,r.y,r.w,r.h);c.strokeStyle='#ce4c32';c.lineWidth=3;c.strokeRect(r.x+b[0]*r.w,r.y+b[1]*r.h,b[2]*r.w,b[3]*r.h);}
    function point(e){var r=canvas.getBoundingClientRect();return {x:Math.max(0,Math.min(1,((e.clientX-r.left)*canvas.width/r.width-canvasRect.x)/canvasRect.w)),y:Math.max(0,Math.min(1,((e.clientY-r.top)*canvas.height/r.height-canvasRect.y)/canvasRect.h))};}
    canvas.addEventListener('pointerdown',function(e){if(!canvasRect)return;drag=point(e);canvas.setPointerCapture(e.pointerId);});
    canvas.addEventListener('pointermove',function(e){if(!drag)return;var p=point(e);slot(state.cropTarget).crop=[Math.min(drag.x,p.x),Math.min(drag.y,p.y),Math.abs(p.x-drag.x),Math.abs(p.y-drag.y)];paintCanvas();});
    canvas.addEventListener('pointerup',function(){if(!drag)return;drag=null;var s=slot(state.cropTarget);if(s.crop[2]<.02||s.crop[3]<.02)s.crop=[0,0,1,1];s.cutout='';drawCrop();changed();});
    canvas.addEventListener('pointercancel',function(){drag=null;drawCrop();});
    async function removeBackground(){if(!state.cropTarget)return;cut.disabled=true;var pid=state.cropTarget,s=slot(pid),box=s.crop.slice();status.textContent='Removing the background from your selected subject…';try{await host.ready();var d=await host.post('/cards/cutouts',{photo_id:pid,crop:box});if(JSON.stringify(slot(pid).crop)!==JSON.stringify(box))throw Error('Crop changed. Select the subject again.');s.cutout=d.cutout_id;drawCrop();changed();status.textContent='Check the cutout, then save your card.';}catch(e){error(e);}finally{cut.disabled=false;}}
    async function uploadFiles(files){for(var f of Array.from(files).slice(0,20)){var row=el('div',f.name+' — waiting','oc-upload');uploads.append(row);await uploadOne(f,row);}await refresh();}
    async function uploadOne(f,row){row.replaceChildren(el('span',f.name+' — uploading…'));try{var d=await host.upload(f);row.textContent=f.name+' — saved';if(!state.selected.includes(d.photo.id)&&state.selected.length<5)state.selected.push(d.photo.id);}catch(e){row.replaceChildren(el('span',f.name+' — '+e.message),button('Retry',async function(){await uploadOne(f,row);await refresh();}));}}
    file.addEventListener('change',function(){uploadFiles(file.files);file.value='';});
    library.addEventListener('dragover',function(e){e.preventDefault();});library.addEventListener('drop',function(e){e.preventDefault();uploadFiles(e.dataTransfer.files);});
    function changed(){state.dirty++;video.hidden=true;video.pause();video.removeAttribute('src');downloads.replaceChildren();spreadWrap.hidden=true;empty.textContent='Edits pending — preview will update after saving.';price.textContent=cardPrice+' fixed per card';clearTimeout(timer);timer=setTimeout(function(){if(tpl()&&chosen().length>=tpl().min_photos)savePreview().catch(error);},850);}
    Object.values(inputs).forEach(function(n){n.addEventListener('input',changed);});
    format.addEventListener('change',function(){state.format=format.value;changed();});
    function money(c){return '£'+(c/100).toFixed(2);}
    function savePreview(){clearTimeout(timer);var snap=spec(),stamp=state.dirty;
      var task=state.chain.catch(function(){}).then(async function(){await host.ready();status.textContent='Saving your card…';var b={spec:snap,via:'ui'};if(state.id){b.id=state.id;b.expected_revision=state.revision;}var d=await host.post('/cards/designs',b);state.id=d.design.id;state.revision=d.design.revision;if(state.dirty===stamp)quality.textContent=(d.warnings||[]).join(' ');await savedList();var j=await host.post('/cards/'+state.id+'/render',{revision:state.revision,kind:'preview'});j=await poll(j.job);if(state.dirty===stamp){preview.src=host.asset(j.url);preview.hidden=false;insidePreview.src=host.asset('/cards/'+state.id+'/r'+state.revision+'/inside');insidePreview.hidden=false;empty.textContent='Saved revision '+state.revision+' · front and inside';status.textContent='Saved. Your card and video use this same scene.';}return {id:d.design.id,revision:d.design.revision,stamp:stamp};});state.chain=task;return task;
    }
    async function poll(job){for(var i=0;i<100;i++){if(job.status==='ready')return job;if(job.status==='failed')throw Error(job.error||'Render failed. Retry the same saved card.');await wait(600);var d=await host.get('/cards/jobs/'+job.id);job=d.job;}throw Error('Still rendering. Click again to check the existing job.');}
    function paintFonts(){[headlineFont,insideFont].forEach(function(sel){sel.replaceChildren();Object.keys(state.fonts).forEach(function(fid){var f=state.fonts[fid];sel.append(new Option(f.label+' — '+f.mood,fid));});});headlineFont.value=state.headlineFont;insideFont.value=state.insideFont;}
    async function showSpread(){if(!state.id)throw Error('Save the card first.');spreadBtn.disabled=true;try{status.textContent='Rendering all four faces…';var r=await host.post('/cards/'+state.id+'/render',{revision:state.revision,kind:'spread'});var j=await poll(r.job);spreadParts.forEach(function(p){spreadImgs[p[0]].src=host.asset(j.urls[p[0]]);});try{triptychImg.src=host.asset('/cards/'+state.id+'/r'+state.revision+'/triptych');}catch(e){}spreadWrap.hidden=false;status.textContent='Front, inside and back — this exact proof is what '+cardPrice+' buys.';}finally{spreadBtn.disabled=false;}}
    async function produce(kind){var btn=kind==='motion'?motionBtn:exportBtn;btn.disabled=true;try{var savedCard=await savePreview();status.textContent=kind==='motion'?'Bringing the scene to life…':'Building the print artwork…';var d=await host.post('/cards/'+savedCard.id+'/render',{revision:savedCard.revision,kind:kind});var j=await poll(d.job);if(state.dirty!==savedCard.stamp)throw Error('Your edits changed while rendering. Save the new version first.');var url=host.asset(j.url);if(kind==='motion'){video.src=url;video.hidden=false;}var a=el('a',kind==='motion'?'Download matching MP4':'Download print PDF','oc-button');a.href=url;a.download=kind==='motion'?'oddhobb-scene.mp4':'oddhobb-card.pdf';downloads.append(a);status.textContent=kind==='motion'?'Your matching clip is ready.':'PDF ready: 300 dpi, 3 mm bleed. Check against your print supplier’s specification.';return savedCard;}finally{btn.disabled=false;}}
    var idem='';
    async function buy(){orderBtn.disabled=true;try{var sc=await produce('export');idem=sc.id+'-r'+sc.revision+'-qty1';var d=await host.post('/cards/'+sc.id+'/checkout',{revision:sc.revision,qty:1,idempotency_key:idem});status.textContent='Ready to buy · taking you to checkout to pay…';location.href=d.checkout_url;}catch(e){error(e);}finally{orderBtn.disabled=false;}}
    async function reserve(){orderBtn.disabled=true;try{var sc=await produce('export');idem=sc.id+'-r'+sc.revision+'-qty1';var d=await host.post('/cards/'+sc.id+'/order',{revision:sc.revision,qty:1,idempotency_key:idem});status.textContent='Card reserved · '+money(d.order.price_cents)+' fixed · no payment taken. '+d.order.id;try{if(typeof siteShell!=="undefined"&&siteShell.refreshBadge)siteShell.refreshBadge();}catch(e){}}catch(e){error(e);}finally{orderBtn.disabled=false;}}
    async function savedList(){var d=await host.get('/cards/designs');saved.replaceChildren(new Option('New card',''));d.designs.forEach(function(x){saved.append(new Option(x.spec.headline+' · r'+x.revision,x.id));});saved.value=state.id;}
    async function loadSaved(selectedId, wantRev){clearTimeout(timer);await state.chain.catch(function(){});if(!selectedId){newCard();return;}try{var d=await host.get('/cards/designs/'+selectedId),x=d.design;state.id=x.id;state.revision=(wantRev&&wantRev>=1&&wantRev<=x.revision)?wantRev:x.revision;if(state.revision!==x.revision){try{var frozen=(await host.get('/cards/'+state.id+'/scene?revision='+state.revision)).scene;if(frozen&&frozen.spec)x.spec=frozen.spec;}catch(e){}}state.template=x.spec.template;state.format=x.spec.format;state.headlineFont=x.spec.headline_font||'fraunces';state.insideFont=((x.spec.inside||{}).right||{}).font||'inter';state.selected=x.spec.photos.map(function(p){state.slots[p.photo_id]=p;return p.photo_id;});Object.keys(inputs).forEach(function(k){inputs[k].value=x.spec[k];});format.value=state.format;headlineFont.value=state.headlineFont;insideFont.value=state.insideFont;paintChoices();paintPhotos();paintCropChoices();state.dirty++;downloads.replaceChildren();video.pause();video.hidden=true;video.removeAttribute('src');preview.hidden=true;insidePreview.hidden=true;price.textContent=cardPrice+' fixed per card';status.textContent='Opened saved revision '+state.revision+'.';empty.textContent='Saved revision '+state.revision;var scene=(await host.get('/cards/'+state.id+'/scene?revision='+state.revision)).scene;if(scene.poster.url){preview.src=host.asset(scene.poster.url);preview.hidden=false;insidePreview.src=host.asset('/cards/'+state.id+'/r'+state.revision+'/inside');insidePreview.hidden=false;}if(scene.outputs.spread&&scene.outputs.spread.status==='ready'){spreadParts.forEach(function(p){spreadImgs[p[0]].src=host.asset(scene.outputs.spread.urls[p[0]]);});triptychImg.src=host.asset('/cards/'+state.id+'/r'+state.revision+'/triptych');spreadWrap.hidden=false;}if(scene.outputs.motion.status==='ready'){video.src=host.asset(scene.outputs.motion.url);video.hidden=false;}}catch(e){error(e);}}
    saved.addEventListener('change',function(){loadSaved(saved.value);});
    function newCard(){clearTimeout(timer);state.chain.catch(function(){}).then(function(){state.id='';state.revision=0;state.dirty++;saved.value='';video.hidden=true;downloads.replaceChildren();status.textContent='New card. Choose a scene and edit your message.';var ctx=window.OddHobbStudioContext;if(ctx)document.dispatchEvent(new CustomEvent('oddhobb:subject',{detail:ctx}));});}
    function open(){if(!state.ready)state.ready=host.ready().then(async function(){var d=await host.get('/cards/templates');if(d.product&&d.product.price){cardPrice=d.product.price;orderBtn.textContent='Buy this card · '+cardPrice;}state.templates=d.templates;state.formats=d.formats;format.replaceChildren();Object.keys(d.formats).forEach(function(k){format.append(new Option(d.formats[k].label,k));});format.value=state.format;headline.value=tpl().headline;motionBtn.disabled=!d.motion_available;try{var f=await host.get('/cards/fonts');state.fonts=f.fonts||{};paintFonts();}catch(e){}paintChoices();await refresh();await savedList();price.textContent=cardPrice+' fixed per card';}).catch(function(e){state.ready=null;error(e);});return state.ready;}
    var videoHost=document.querySelector('#panel-cards .panel__inner');
    var sceneLibrary=el('section',undefined,'oc-scene-library');
    var sceneGrid=el('div',undefined,'oc-scenes');
    var videoStatus=el('p','','oc-status');videoStatus.setAttribute('role','status');videoStatus.setAttribute('aria-live','polite');
    var videoRefresh=button('Refresh saved scenes',function(){videos();});
    sceneLibrary.append(el('h3','Your card scenes'),el('p','The same saved scene makes your card and matching video. Render the video from its card.'),videoRefresh,sceneGrid,videoStatus);
    if(videoHost){
      // Gallery (ready-made, no forms) + scenes are the Cards tab.
      // The editor below stays for tinkerers; backend flows untouched.
      var galHost={get:host.get,post:host.post,asset:host.asset};
      if(window.OddHobbGallery&&!videoHost.querySelector('.oc-gallery')){
        try{window.OddHobbGallery.mount(videoHost,galHost);}catch(e){}
      }
      videoHost.insertBefore(sceneLibrary,videoHost.children[1]||null);
    }
    var videoGeneration=0;
    async function videos(focusId){var generation=++videoGeneration;videoStatus.textContent='Loading your saved scenes…';try{await host.ready();var d=await host.get('/cards/designs');var scenes=await Promise.all(d.designs.map(function(x){return host.get('/cards/'+x.id+'/scene?revision='+x.revision).then(function(r){return r.scene;});}));if(generation!==videoGeneration)return;sceneGrid.replaceChildren();scenes.forEach(function(scene){var item=el('article',undefined,'oc-scene');item.dataset.sceneId=scene.id;item.append(el('h4',scene.spec.headline),el('p','Saved revision '+scene.revision));if(scene.poster.url){var poster=el('img');poster.src=host.asset(scene.poster.url);poster.alt=scene.spec.headline;poster.loading='lazy';item.append(poster);}var clip=el('video');clip.controls=true;clip.playsInline=true;clip.preload='none';clip.hidden=true;var message=el('p','','oc-status');message.setAttribute('role','status');
      function showClip(url){clip.src=host.asset(url);clip.hidden=false;var a=el('a','Download MP4','oc-button');a.href=clip.src;a.download='oddhobb-scene.mp4';links.append(a);}
      var links=el('div',undefined,'oc-toolbar');var render=button('Render matching video',async function(){render.disabled=true;message.textContent='Rendering this saved revision…';try{var r=await host.post('/cards/'+scene.id+'/render',{revision:scene.revision,kind:'motion'});var job=await poll(r.job);showClip(job.url);render.hidden=true;message.textContent='Video ready · revision '+scene.revision;}catch(e){message.textContent=e.message;}finally{render.disabled=false;}});
      links.append(button('Open linked card',async function(){try{await open();await refresh();await loadSaved(scene.id);host.tab('cards');}catch(e){message.textContent=e.message;}}),render);item.append(clip,links,message);var motion=scene.outputs.motion;if(motion.status==='ready'){showClip(motion.url);render.hidden=true;}else{render.disabled=!scene.capabilities.video;message.textContent=motion.status==='failed'?motion.error:motion.status==='queued'||motion.status==='running'?'Video is rendering. Click to check the existing job.':'Create the matching video from this card.';}sceneGrid.append(item);});videoStatus.textContent=scenes.length?'Each video stays linked to its saved card revision.':'No saved scenes yet. Make your first card in Studio.';if(focusId){var focused=Array.from(sceneGrid.children).find(function(n){return n.dataset.sceneId===focusId;});if(focused)focused.scrollIntoView({block:'start'});}}catch(e){if(generation===videoGeneration)videoStatus.textContent=e.message;}}
    document.addEventListener('oddhobb:subject',function(e){
      var ctx=e.detail;if(state.id){status.textContent='This saved card keeps its original photos. Choose New card to make one for '+(ctx.subject?ctx.subject.name:'another friend')+'.';return;}
      state.selected=ctx.photos.slice(0,5).map(function(p){var link=p.subjects.find(function(l){return l.subject_id===ctx.subject.id&&l.confirmed&&l.face_id;});var face=link&&p.faces.find(function(f){return f.id===link.face_id;});if(face){var s=slot(p.id);s.focus=[face.box[0]+face.box[2]/2,face.box[1]+face.box[3]/2];}return p.id;});
      recipient.value=ctx.subject?ctx.subject.name:'';paintPhotos();paintCropChoices();
    });
    async function openDesign(id, revision){await open();await refresh();await loadSaved(id, revision);}
    if(window.OddHobbViralCards&&panel){
      try{window.OddHobbViralCards.mount(panel,host);}catch(e){}
    }
    return {open:open,refresh:refresh,videos:videos,openDesign:openDesign,showSpread:showSpread};
  };
})();
