(function(){
  'use strict';
  function node(tag,text,cls){var n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
  function link(text,path){var a=node('a',text,'oc-button');a.href=path;a.dataset.route='';return a;}
  function setBadge(n){var el=document.getElementById('cart-n');if(el)el.textContent=String(n);}
  function setAcctName(t){var el=document.getElementById('acct-name');if(el)el.textContent=t;}
  window.OddHobbShell=function(host){
    var accountDialog=node('dialog',undefined,'studio-dialog');accountDialog.id='account-dialog';
    var inner=node('div',undefined,'studio-dialog-inner'),close=node('button','Close','studio-dialog-close');close.type='button';close.onclick=function(){accountDialog.close();};
    inner.append(close,node('h2','Your OddHobb account'),node('p','Sign in to keep your friends, photos and saved designs together.'));
    ['g-signin','g-who'].forEach(function(id){var n=document.getElementById(id);if(n)inner.append(n);});
    var pwWrap=node('div','oc-password'),pwH=node('input'),pwP=node('input'),pwMsg=node('p','','panel__msg'),pwIn=node('button','Sign in','oc-button'),pwUp=node('button','Create account','oc-button');
    pwWrap.className='oc-password';
    pwH.type='text';pwH.placeholder='handle (e.g. chris)';pwH.autocomplete='username';pwH.style.marginRight='6px';
    pwP.type='password';pwP.placeholder='password (8+ chars)';pwP.autocomplete='current-password';pwP.style.marginRight='6px';
    pwIn.type='button';pwUp.type='button';pwUp.style.marginLeft='6px';
    function pwAuth(mode){
      var handle=pwH.value.trim(),password=pwP.value;
      if(!handle||!password){pwMsg.textContent='Handle + password needed.';return;}
      pwMsg.textContent='Signing in…';pwIn.disabled=pwUp.disabled=true;
      var body={handle:handle,password:password};
      if(window.__FIGG_ANON_OWNER)body.claim_owner=window.__FIGG_ANON_OWNER;
      fetch('/backend/api/accounts'+(mode==='signup'?'':'/login'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(r){return r.json();}).then(function(d){
        pwIn.disabled=pwUp.disabled=false;
        if(!d.ok){pwMsg.textContent=d.error||'Failed.';return;}
        try{localStorage.setItem('pogpet.apikey',d.api_key);localStorage.setItem('pogpet.owner',d.handle);localStorage.removeItem('pogpet.ownersig');}catch(e){}
        location.reload();
      }).catch(function(e){pwIn.disabled=pwUp.disabled=false;pwMsg.textContent=e.message;});
    }
    pwIn.onclick=function(){pwAuth('signin');};pwUp.onclick=function(){pwAuth('signup');};
    pwWrap.append(node('p','Or use a handle + password:'),pwH,pwP,pwIn,pwUp,pwMsg);inner.append(pwWrap);
    inner.append(link('Account and orders','/account'));accountDialog.append(inner);document.body.append(accountDialog);
    var accountPanel=document.getElementById('panel-account');
    if(accountPanel)accountPanel.querySelector('.panel__inner').append(node('h1','Your account'),node('p','Your photos and creations stay with your account.'),link('View basket','/cart'));
    var sign=node('button','Sign in','oc-button');sign.type='button';sign.onclick=openAccount;
    if(accountPanel)accountPanel.querySelector('.panel__inner').append(sign);
    function openAccount(){if(!accountDialog.open)accountDialog.showModal();}
    function paintAcctName(name){setAcctName(name||'sign in');}
    var searchGeneration=0;
    async function search(q){
      var ticket=++searchGeneration,body=document.querySelector('#panel-search .panel__inner');body.replaceChildren(node('h1','Search'),node('p',q?'Results for “'+q+'”':'Type a product or occasion in the search bar.'));
      if(!q)return;
      try{await host.loadProducts();if(ticket!==searchGeneration)return;
        var grid=node('div',undefined,'etsy');host.search(q).forEach(function(r){grid.append(host.searchTile(r));});body.append(grid);
        if(!grid.children.length)body.append(node('p','No matching products yet. Try a different search or tell Oddy what you have in mind.'));
      }catch(e){body.append(node('p',e.message));}
    }
    var cartGeneration=0;
    var acctGeneration=0;
    async function refreshBadge(){
      try{
        await host.ready();
        var result=await host.get('/studio/basket');
        var n=0;result.items.forEach(function(it){n+=Math.max(1,parseInt(it.qty||1,10)||1);});
        setBadge(n);
        return n;
      }catch(e){return 0;}
    }
    async function cart(){
      var ticket=++cartGeneration,body=document.querySelector('#panel-cart .panel__inner');body.replaceChildren(node('h1','Your basket'),node('p','Loading your saved reservations…'));
      try{await host.ready();var result=await host.get('/studio/basket');if(ticket!==cartGeneration)return;body.replaceChildren(node('h1','Your basket'));
        var total=0,count=0;
        result.items.forEach(function(item){
          var qty=Math.max(1,parseInt(item.qty||1,10)||1);count+=qty;
          var row=node('article',undefined,'basket-row');
          row.append(node('h2',item.label),node('p',qty+' × '+String(item.status||'pending_checkout').replaceAll('_',' ')),node('strong','£'+((item.price_cents||0)/100).toFixed(2)));
          if(item.design_id)row.append(link('Open card','/cards/'+item.design_id));
          else if(item.note&&/^design\s+\S+/.test(item.note||'')){
            var did=String(item.note).split(/\s+/)[1].replace(/[(),]/g,'');
            if(did)row.append(link('Open card','/cards/'+did));
          }
          body.append(row);total+=(item.price_cents||0);
        });
        setBadge(count);
        if(result.items.length)body.append(node('p','Reserved items: £'+(total/100).toFixed(2)+'. Shipping is quoted separately.'));
        else body.append(node('p','Your basket is empty. Choose a card or personalised product to get started.'));
        body.append(link('Browse products','/products'),link('Greeting cards','/cards'));
        if(result.items.length)body.append(node('p','These are reservations; you have not been charged. Checkout links appear only when a supplier quote is available.'));
        result.items.filter(function(i){return i.checkout_url;}).forEach(function(i){var a=node('a','Checkout '+i.label,'oc-button');a.href=i.checkout_url;body.append(a);});
      }catch(e){body.replaceChildren(node('h1','Your basket'),node('p',e.message));}
    }
    async function account(ownerHint){
      var ticket=++acctGeneration,body=document.querySelector('#panel-account .panel__inner');
      if(!body)return;
      body.replaceChildren(node('h1','Your account'),node('p','Loading…'));
      try{
        await host.ready();
        var me=null;
        try{me=await host.get('/accounts/me');}catch(e){me=null;}
        var handle=(me&&me.handle)||ownerHint||'';
        paintAcctName(handle?('@'+handle):'sign in');
        body.replaceChildren(node('h1','Your account'));
        if(me&&me.handle){
          body.append(node('p','Signed in as @'+me.handle+(me.display_name?' ('+me.display_name+')':'')));
          if(me.active_mesh_id)body.append(node('p','Active star: '+me.active_mesh_id));
          try{
            var basket=await host.get('/studio/basket');
            var n=0;basket.items.forEach(function(it){n+=Math.max(1,parseInt(it.qty||1,10)||1);});
            setBadge(n);
            body.append(node('p',n?('Basket: '+n+' reserved item'+(n===1?'':'s')):'Basket is empty.'));
          }catch(e){}
          try{
            var orders=await host.get('/studio/orders');
            var list=(orders&&orders.orders)||[];
            if(list.length){
              body.append(node('h2','Recent orders'));
              list.slice(0,5).forEach(function(o){
                body.append(node('p',(o.line||'order').replaceAll('_',' ')+' · '+(o.status||'')+' · £'+((o.price_cents||0)/100).toFixed(2)));
              });
            }
          }catch(e){}
          var out=node('button','Sign out','oc-button');out.type='button';
          out.onclick=function(){try{localStorage.removeItem('pogpet.apikey');localStorage.removeItem('pogpet.ownersig');localStorage.setItem('pogpet.owner','pog_'+Math.random().toString(36).slice(2,10));localStorage.removeItem('pogpet.mesh');}catch(e){}location.reload();};
          body.append(out);
        }else{
          var anon=ownerHint||'';
          body.append(node('p','You are browsing as '+(anon||'a guest')+'. Sign in to keep friends, photos and saved designs together.'));
          body.append(link('View basket','/cart'));
          var s2=node('button','Sign in','oc-button');s2.type='button';s2.onclick=openAccount;body.append(s2);
          paintAcctName('sign in');
        }
      }catch(e){body.replaceChildren(node('h1','Your account'),node('p',e.message));}
    }
    return {openAccount:openAccount,search:search,cart:cart,account:account,refreshBadge:refreshBadge,paintAcctName:paintAcctName};
  };
})();
