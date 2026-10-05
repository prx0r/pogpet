/* Local authoring only: no upload, credentials or external scene launch. */
(function(){
  'use strict';
  var viewer=document.getElementById('performer'),file=document.getElementById('motion-file'),select=document.getElementById('motion-clip'),time=document.getElementById('motion-time'),clock=document.getElementById('motion-clock'),play=document.getElementById('motion-play'),poster=document.getElementById('motion-poster'),status=document.getElementById('status');
  var url='',generation=0,ready=false;
  function controls(enabled){select.disabled=time.disabled=play.disabled=poster.disabled=!enabled;}
  function report(message){status.textContent=message;}
  async function load(f){var stamp=++generation;ready=false;controls(false);if(!f)return;
    try{
      if(!/\.glb$/i.test(f.name)||f.size>64*1024*1024)throw Error('Choose a GLB file up to 64 MB.');
      var buffer=await f.arrayBuffer(),view=new DataView(buffer);
      if(buffer.byteLength<20||view.getUint32(0,true)!==0x46546c67||view.getUint32(4,true)!==2||view.getUint32(8,true)!==buffer.byteLength)throw Error('This is not a complete GLB version 2.');
      var length=view.getUint32(12,true);
      if(view.getUint32(16,true)!==0x4e4f534a||20+length>buffer.byteLength)throw Error('The GLB has no valid JSON chunk.');
      var doc=JSON.parse(new TextDecoder().decode(new Uint8Array(buffer,20,length)));
      if(!doc.skins||!doc.skins.length||!doc.animations||!doc.animations.length)throw Error('Export a skinned character with its animation clips. Static meshes cannot perform body motion.');
      if((doc.buffers||[]).concat(doc.images||[]).some(function(a){return a.uri&&!a.uri.startsWith('data:');}))throw Error('Export a self-contained GLB with embedded buffers and textures.');
      await Promise.race([customElements.whenDefined('model-viewer'),new Promise(function(_,reject){setTimeout(function(){reject(Error('The 3D viewer did not load. Check the local viewer installation.'));},15000);})]);
      if(stamp!==generation)return;
      viewer.pause();if(url)URL.revokeObjectURL(url);url=URL.createObjectURL(new Blob([buffer],{type:'model/gltf-binary'}));viewer.src=url;report('Loading '+f.name+'…');
    }catch(e){if(stamp===generation){viewer.removeAttribute('src');report(e.message);}}
  }
  file.addEventListener('change',function(){load(file.files[0]);});
  viewer.addEventListener('load',function(){select.replaceChildren();(viewer.availableAnimations||[]).forEach(function(name){select.append(new Option(name,name));});if(!select.options.length){report('No playable animation found. Inspect the GLB before using it.');return;}ready=true;controls(true);choose();report('Performance loaded. Check feet, hands and prop contact; choose your card frame.');});
  viewer.addEventListener('error',function(){ready=false;controls(false);report('The performer could not load. Inspect the GLB and its embedded assets.');});
  function update(){time.max=String(viewer.duration||0);time.value=String(viewer.currentTime||0);clock.textContent=Number(time.value).toFixed(2)+' s';}
  function choose(){viewer.pause();viewer.animationName=select.value;viewer.currentTime=0;time.value='0';play.textContent='Play';requestAnimationFrame(update);}
  select.addEventListener('change',choose);
  play.addEventListener('click',function(){if(!ready)return;if(viewer.paused){viewer.play();play.textContent='Pause';}else{viewer.pause();play.textContent='Play';}});
  time.addEventListener('input',function(){viewer.pause();play.textContent='Play';viewer.currentTime=Number(time.value);clock.textContent=Number(time.value).toFixed(2)+' s';});
  viewer.addEventListener('ar-status',function(e){if(e.detail.status==='failed')report('AR placement failed. Use the 3D preview or try a supported device.');});
  poster.addEventListener('click',async function(){poster.disabled=true;try{viewer.pause();play.textContent='Play';var blob=await viewer.toBlob();var download=URL.createObjectURL(blob),a=document.createElement('a');a.href=download;a.download='oddhobb-rehearsal-poster.png';document.body.append(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(download);},30000);report('Poster downloaded at '+viewer.currentTime.toFixed(2)+' s. Apply the card layout for print.');}catch(e){report('Could not export the poster: '+e.message);}finally{poster.disabled=!ready;}});
  setInterval(function(){if(ready&&!viewer.paused)update();},100);
  window.addEventListener('pagehide',function(){if(url)URL.revokeObjectURL(url);});
})();
