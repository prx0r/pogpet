/* The selected person owns the page context. Photos can have many people. */
(function () {
  'use strict';
  function node(tag,text,cls){var n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
  function button(text,fn,cls){var b=node('button',text,cls||'oc-button');b.type='button';b.onclick=fn;return b;}
  window.OddHobbPeople=function(host){
    var data={subjects:[],photos:[],meshes:[]}, selected='',filter='all',generation=0,swiper,worker,workerId=0;
    var loaded=false, working=false, inflight=null, selectionChain=Promise.resolve(), memories={};
    var friends=document.getElementById('friends'),grid=document.getElementById('as-grid');
    var status=document.getElementById('as-status'),heading=document.getElementById('studio-photo-title');
    var meshHeading=document.getElementById('studio-mesh-title'), controls=document.getElementById('studio-photo-controls');
    var input=node('input');input.type='file';input.accept='image/jpeg,image/png,image/webp';input.multiple=true;input.hidden=true;
    var upload=button('Add photos',function(){input.click();});upload.id='studio-upload';
    var detect=button('Find faces',function(){detectPending().catch(error);});
    controls.replaceChildren(upload,input,detect,button('Refresh',function(){refresh().catch(error);}));
    var filters=node('div',undefined,'studio-filters');controls.after(filters);
    [['all','All'],['portraits','Portraits'],['together','Together'],['activities','Activities'],['favourites','Favourites'],['review','Review faces']].forEach(function(f){
      var b=button(f[1],function(){filter=f[0];paintPhotos();},'studio-filter');b.dataset.filter=f[0];filters.append(b);
    });
    document.getElementById('studio-add-friend').onclick=function(){createFriend().catch(error);};
    function available(value){upload.disabled=!value||working;detect.disabled=!value||working;document.getElementById('studio-add-friend').disabled=!value||working;}
    available(false);
    function error(e){status.textContent=e.message||String(e);if(!loaded){host.clearMesh();host.renderMeshes([]);document.getElementById('studio-mesh-empty').hidden=true;available(false);grid.replaceChildren(node('p','Your photos will appear here when the library is available.','studio-empty'));}}

    function person(){return data.subjects.find(function(s){return s.id===selected;});}
    function belongs(p){return p.subjects.some(function(s){return s.subject_id===selected&&s.confirmed;});}
    function subjectPhotos(sid){return data.photos.filter(function(p){return p.subjects.some(function(s){return s.subject_id===sid&&s.confirmed;});});}
    function context(){var s=person();return {subject:s||null,photos:s?subjectPhotos(s.id):[],meshId:host.meshId()};}
    function publish(){window.OddHobbStudioContext=context();document.dispatchEvent(new CustomEvent('oddhobb:subject',{detail:context()}));}
    function paintFriends(){
      if(swiper){swiper.destroy(true,true);swiper=null;}
      friends.replaceChildren();friends.className='friends swiper';
      var wrap=node('div',undefined,'swiper-wrapper');friends.append(wrap);
      data.subjects.forEach(function(s,i){
        var slide=node('div',undefined,'swiper-slide');var b=button('',function(){if(swiper)swiper.slideTo(i);commit(s.id);},'friend');
        b.setAttribute('role','option');b.setAttribute('aria-selected',String(selected===s.id));b.setAttribute('aria-label',s.name);b.dataset.subjectId=s.id;
        var photos=subjectPhotos(s.id),photo=photos[0]||data.photos.find(function(p){return p.subjects.some(function(l){return l.subject_id===s.id;});});
        if(photo){var img=node('img');var link=photo.subjects.find(function(l){return l.subject_id===s.id&&l.face_id;});img.src=host.asset(photo.thumbnail_url+(link?'&face_id='+encodeURIComponent(link.face_id):''));img.alt='';img.loading='lazy';b.append(img);}else b.append(node('span',s.kind==='pet'?'🐾':s.name.slice(0,1),'friend-initial'));
        b.append(node('span',s.name,'friend-name'));slide.append(b);wrap.append(slide);
      });
      if(!data.subjects.length){friends.append(node('p','Add a friend, upload photos, then confirm who appears in them.','studio-empty'));
        // demo friend: Nibble with her original photo, so the page is never empty
        host.get('/studio/demo').then(function(dd){
          if(!dd||!dd.ok||!dd.demo||data.subjects.length)return;
          var card=node('button','Demo: meet '+dd.demo.name+' — our sample friend, ready to try the shelf.','friend');
          card.type='button';
          if(dd.demo.photo&&dd.demo.photo.url){var im=node('img');im.src=host.asset(dd.demo.photo.url);im.alt=dd.demo.name+' original photo';im.loading='lazy';im.style.cssText='width:72px;height:72px;object-fit:cover;border-radius:50%';card.prepend(im);}
          card.onclick=function(){window.OddHobbRouter.navigate('/products');};
          friends.append(card);
        }).catch(function(){});return;}
      if(window.Swiper){
        var index=Math.max(0,data.subjects.findIndex(function(s){return s.id===selected;}));
        var dragging=false;
        swiper=new Swiper(friends,{slidesPerView:'auto',spaceBetween:18,centeredSlides:true,initialSlide:index,
          freeMode:{enabled:true,momentum:true,sticky:true},speed:matchMedia('(prefers-reduced-motion: reduce)').matches?0:320,
          keyboard:{enabled:true,onlyInViewport:true},a11y:{enabled:true},
          on:{touchStart:function(){dragging=true;},transitionEnd:function(s){if(dragging){dragging=false;var p=data.subjects[s.activeIndex];if(p)commit(p.id);}},touchEnd:function(s){setTimeout(function(){if(!s.animating&&dragging){dragging=false;var p=data.subjects[s.activeIndex];if(p)commit(p.id);}},100);}}
        });
      }
      friends.onkeydown=function(e){if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();var at=data.subjects.findIndex(function(s){return s.id===selected;});at=Math.max(0,Math.min(data.subjects.length-1,at+(e.key==='ArrowRight'?1:-1)));if(swiper)swiper.slideTo(at);commit(data.subjects[at].id);}};
    }
    function commit(sid){if(sid===selected)return;try{if(navigator.vibrate&&!matchMedia('(prefers-reduced-motion: reduce)').matches)navigator.vibrate(8);}catch(e){}window.OddHobbRouter.navigate('/studio/people/'+sid);}
    function apply(sid){
      if(sid&&!data.subjects.some(function(s){return s.id===sid;})){host.renderMeshes([]);grid.replaceChildren(node('p','This friend was not found.','studio-empty'));return;}
      selected=sid||'';
      // No friend picked yet: show every mesh by default. Picking a friend
      // narrows the shelf to theirs; unassigned stay under the assign box.
      var meshes=selected?data.meshes.filter(function(m){return m.subject_id===selected;}):data.meshes.slice(),mid=memories[selected]||'';
      if(!meshes.some(function(m){return m.id===mid;}))mid=(meshes.find(function(m){return m.status==='succeeded';})||{}).id||'';
      host.clearMesh();host.renderMeshes(meshes,mid);paintUnassignedMeshes();paintPhotos();publish();
      var s=person();meshHeading.textContent=s?s.name+'’s meshes':'Meshes';
      var empty=document.getElementById('studio-mesh-empty');
      if(empty&&!meshes.length)empty.textContent=selected?'No meshes for this friend yet. Choose one of their photos to create a character.':'No meshes yet. Upload a photo to create your first character.';
      friends.querySelectorAll('[data-subject-id]').forEach(function(b){b.setAttribute('aria-selected',String(b.dataset.subjectId===selected));});
      // Serialize writes: a slow Dad request can never overwrite a newer Mum selection.
      selectionChain=selectionChain.catch(function(){}).then(function(){return host.post('/studio/selection',{subject_id:sid||'',mesh_id:mid});}).catch(error);
    }
    function paintUnassignedMeshes(){
      var box=document.getElementById('studio-unassigned-meshes');box.replaceChildren();
      var unassigned=data.meshes.filter(function(m){return !m.subject_id;});
      if(!unassigned.length)return;
      var details=node('details',undefined,'unassigned-meshes');details.append(node('summary','Assign existing meshes ('+unassigned.length+')'));
      unassigned.forEach(function(m){var label=node('label','Character '+m.id.replace('msh_','').slice(0,6));var select=node('select');select.append(new Option('Whose character is this?',''));data.subjects.forEach(function(s){select.append(new Option(s.name,s.id));});select.onchange=async function(){if(!select.value)return;select.disabled=true;try{await host.post('/studio/meshes/'+m.id+'/subject',{subject_id:select.value});await refresh();}catch(e){select.disabled=false;error(e);}};label.append(select);details.append(label);});box.append(details);
    }
    async function refresh(sid){
      var ticket=++generation;await host.ready();var result=await host.get('/studio/library');
      if(ticket!==generation)return;
      data=result;loaded=true;available(true);
      var current=window.OddHobbRouter.current;
      var wanted=sid!==undefined?sid:current&&current.subjectId;
      if(!wanted)wanted=selected||(result.selection||{}).subject_id||(data.subjects[0]||{}).id||'';
      if(result.selection&&result.selection.mesh_id)memories[result.selection.subject_id]=result.selection.mesh_id;
      selected=wanted;paintFriends();apply(wanted);
    }
    async function open(sid){
      try{if(!loaded){if(!inflight)inflight=refresh(sid).finally(function(){inflight=null;});await inflight;var current=window.OddHobbRouter.current;if(current&&current.tab==='studio'&&current.subjectId&&current.subjectId!==selected){apply(current.subjectId);paintFriends();}}
      else {apply(sid||selected||(data.subjects[0]||{}).id||'');paintFriends();}}catch(e){error(e);throw e;}
    }
    function paintPhotos(){
      var s=person();heading.textContent=s?s.name+'’s photos':'Photos';
      var photos=filter==='review'?data.photos.filter(function(p){return !p.subjects.length||p.subjects.some(function(l){return !l.confirmed;})||p.faces.some(function(f){return !p.subjects.some(function(l){return l.face_id===f.id&&l.confirmed;});});}):data.photos.filter(belongs);
      if(filter==='favourites')photos=photos.filter(function(p){return p.favourite;});
      if(filter==='together')photos=photos.filter(function(p){return p.faces.length>1||new Set(p.subjects.map(function(s){return s.subject_id;})).size>1;});
      if(filter==='portraits')photos=photos.filter(function(p){return p.faces.length===1||p.tags.includes('portrait');});
      if(filter==='activities')photos=photos.filter(function(p){return p.tags.includes('activity');});
      filters.querySelectorAll('button').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.filter===filter));});
      grid.replaceChildren();grid.className='studio-photo-grid';
      photos.forEach(function(p){var b=button('',function(){editPhoto(p).catch(error);},'studio-photo');b.disabled=working;var im=node('img');im.src=host.asset(p.thumbnail_url);im.alt=p.orig_name||'Uploaded photo';im.loading='lazy';b.append(im,node('span',(p.favourite?'★ ':'')+p.orig_name,'studio-photo-caption'));grid.append(b);});
      if(!photos.length)grid.append(node('p',filter==='review'?'All detected faces are reviewed.':s?'No matching photos yet. Add photos or open Review faces to assign '+s.name+'.':'Upload photos, then name the faces you recognise.','studio-empty'));
      status.textContent=photos.length+' photos'+(s?' featuring '+s.name:'');
    }
    function dialog(title){var d=node('dialog',undefined,'studio-dialog');var box=node('div',undefined,'studio-dialog-inner');var close=button('Close',function(){d.close();},'studio-dialog-close');box.append(close,node('h2',title));d.append(box);document.body.append(d);d.addEventListener('close',function(){d.remove();});d.showModal();return {dialog:d,box:box};}
    async function createFriend(){
      var view=dialog('Add a friend');var label=node('label','Name');var field=node('input');field.maxLength=60;label.append(field);var kind=node('select');kind.append(new Option('Person','person'),new Option('Pet','pet'));var msg=node('p');var save=button('Add friend',async function(){save.disabled=true;try{var result=await host.post('/studio/subjects',{name:field.value,kind:kind.value});view.dialog.close();await refresh(result.subject.id);window.OddHobbRouter.navigate('/studio/people/'+result.subject.id);}catch(e){msg.textContent=e.message;save.disabled=false;}});view.box.append(label,kind,save,msg);field.focus();
    }
    async function editPhoto(p){
      var view=dialog('Who’s in this photo?'),imgWrap=node('div',undefined,'studio-photo-inspect'),im=node('img');im.src=host.asset(p.thumbnail_url);im.alt=p.orig_name;imgWrap.append(im);view.box.append(imgWrap);
      var selectors=[],checks=[],faces=p.faces.length?p.faces:[{id:'',box:null}];
      faces.forEach(function(f,i){
        if(f.box){var mark=node('span',String(i+1),'studio-face-box');mark.style.left=(f.box[0]*100)+'%';mark.style.top=(f.box[1]*100)+'%';mark.style.width=(f.box[2]*100)+'%';mark.style.height=(f.box[3]*100)+'%';imgWrap.append(mark);}
        var label=node('label',f.id?'Face '+(i+1):'Main person or pet');var select=node('select');select.setAttribute('aria-label',f.id?'Face '+(i+1):'Main person or pet');select.append(new Option('Not assigned',''));
        data.subjects.forEach(function(s){select.append(new Option(s.name,s.id));});var link=p.subjects.find(function(l){return l.face_id===f.id;});select.value=link?link.subject_id:'';label.append(select);view.box.append(label);selectors.push({face_id:f.id,select:select});
      });
      if(p.faces.length){var more=node('fieldset');more.append(node('legend','Also in the photo (pets or missed faces)'));data.subjects.forEach(function(s){var l=node('label',s.name);var c=node('input');c.type='checkbox';c.checked=p.subjects.some(function(a){return a.subject_id===s.id&&!a.face_id;});l.prepend(c);more.append(l);checks.push({id:s.id,input:c});});view.box.append(more);}
      view.box.append(node('p','Confirm identities before these photos are used automatically. You can correct them at any time.'));
      var favourite=node('input');favourite.type='checkbox';favourite.checked=!!p.favourite;var favLabel=node('label','Favourite');favLabel.prepend(favourite);view.box.append(favLabel);
      var tags=node('input');tags.value=p.tags.join(', ');var tagLabel=node('label','Tags (portrait, activity, celebration…)');tagLabel.append(tags);view.box.append(tagLabel);
      var msg=node('p');var save=button('Save photo',async function(){save.disabled=true;try{
        var links=selectors.filter(function(s){return s.select.value;}).map(function(s){return {subject_id:s.select.value,face_id:s.face_id};});checks.forEach(function(c){if(c.input.checked)links.push({subject_id:c.id,face_id:''});});
        await host.post('/studio/photos/'+p.id,{subjects:links,favourite:favourite.checked,tags:tags.value.split(',').map(function(t){return t.trim();}).filter(Boolean)});
        view.dialog.close();await refresh();
      }catch(e){msg.textContent=e.message;save.disabled=false;}});view.box.append(save,msg);
      var current=person();
      if(current&&belongs(p)){
        view.box.append(node('p','Create a character from this photo using your sculpt allowance. 3 angles of the same person sculpt better — upload front, side and back first, or sculpt this single view now.'));
        var sculpt=button('Create character for '+current.name,async function(){sculpt.disabled=true;try{
          if(p.faces.length>1)throw Error('Choose a single-person photo for sculpting. You can still use this group photo in cards.');
          var result=await host.post('/meshes',{photo_id:p.id,single:true});var mesh=result.mesh||{};
          if(mesh.id)await host.post('/studio/meshes/'+mesh.id+'/subject',{subject_id:current.id});
          msg.textContent='Character queued. Refresh Studio to check its progress.';await refresh();
        }catch(e){msg.textContent=e.message;sculpt.disabled=false;}});view.box.append(sculpt);
      }
    }
    var jobs=new Map();
    function findFaces(bitmap){
      if(!worker){worker=new Worker('/js/face-worker.js?v=studio-2');worker.onmessage=function(e){var job=jobs.get(e.data.id);if(job){jobs.delete(e.data.id);clearTimeout(job.timer);e.data.error?job.reject(Error(e.data.error)):job.resolve(e.data.faces);}};worker.onerror=function(){jobs.forEach(function(j){clearTimeout(j.timer);j.reject(Error('Face detection unavailable. Assign people manually in Review faces.'));});jobs.clear();worker.terminate();worker=null;};}
      return new Promise(function(resolve,reject){var id=++workerId;var timer=setTimeout(function(){jobs.delete(id);if(worker){worker.terminate();worker=null;}reject(Error('Face detection timed out. You can still assign people manually.'));},45000);jobs.set(id,{resolve:resolve,reject:reject,timer:timer});worker.postMessage({id:id,bitmap:bitmap},[bitmap]);});
    }
    async function detectPending(){
      var wasWorking=working;working=true;available(loaded);paintPhotos();try{await host.ready();if(!loaded)await refresh();
        var pending=data.photos.filter(function(p){return p.detection_status==='pending';});
        for(var p of pending){status.textContent='Finding faces in '+p.orig_name+'…';var response=await fetch(host.asset(p.url));if(!response.ok)throw Error('Photo could not be loaded.');var bitmap=await createImageBitmap(await response.blob());var faces=await findFaces(bitmap);await host.post('/studio/photos/'+p.id,{faces:faces});}
        await refresh();filter='review';paintPhotos();
      }finally{working=wasWorking;available(loaded);paintPhotos();}
    }
    input.onchange=async function(){var files=Array.from(input.files);input.value='';var failure=null;working=true;available(loaded);paintPhotos();try{
      for(var f of files){status.textContent='Uploading '+f.name+'…';await host.upload(f);}
      await refresh();await detectPending();
    }catch(e){failure=e;filter='review';}finally{working=false;available(loaded);paintPhotos();if(failure)error(failure);}};
    return {open:open,refresh:refresh,context:context,rememberMesh:function(mid){var sid=selected;memories[sid]=mid;publish();selectionChain=selectionChain.catch(function(){}).then(function(){return host.post('/studio/selection',{subject_id:sid,mesh_id:mid});}).catch(error);}};
  };
})();
