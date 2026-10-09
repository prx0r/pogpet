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
      var ticket=++cartGeneration,body=document.querySelector('#panel-cart .panel__inner');body.replaceChildren(node('h1','Your basket'),node('p','Loading…'));
      function money(c){return '£'+(c/100).toFixed(2);}
      function viewsRow(views){
        if(!views||!views.length)return null;
        var faces=node('div',undefined,'basket-faces');
        views.forEach(function(v){
          var fi=node('img');fi.alt=v.label||v.id;fi.loading='lazy';
          fi.src=(v.url.indexOf('/api/')===0)?host.asset(v.url):v.url;
          fi.onerror=function(){fi.remove();};faces.append(fi);
        });
        return faces;
      }
      function lineViews(at){
        if(at.design_id&&at.design_id.indexOf('card_')===0&&at.revision){
          var b='/cards/'+at.design_id+'/r'+at.revision;
          return [{id:'front',label:'Front',url:b+'/preview'},{id:'inside',label:'Inside',url:b+'/inside'},{id:'back',label:'Back',url:b+'/back'}];
        }
        if(at.line){
          var c='/img/prod/'+at.line;
          return [{id:'front',label:'Front',url:c+'-front.png'},{id:'detail',label:'Detail',url:c+'-hero.png'},{id:'back',label:'Back',url:c+'-back.png'}];
        }
        return [];
      }
      try{
        await host.ready();
        var count=0;
        // ── 1. the one true basket: Shopify cart ──
        var cid=null;try{cid=localStorage.getItem('oddhobb.cartId');}catch(e){cid=null;}
        var shopCount=0,shopTotal=0,shopCheckout='';
        if(cid){
          try{
            var sc=await host.get('/cart?id='+encodeURIComponent(cid));
            var cart=sc.cart||{};
            shopCheckout=cart.checkoutUrl||'';
            var edges=(((cart.lines||{}).edges)||[]);
            if(edges.length)body.append(node('h2','Your basket'));
            edges.forEach(function(e){
              var n=e.node||{},at={};(n.attributes||[]).forEach(function(a){at[a.key]=a.value;});
              var qty=Math.max(1,n.quantity||1);shopCount+=qty;
              var unit=parseFloat((((n.merchandise||{}).price||{}).amount)||'0')||0;
              shopTotal+=unit*qty;
              var row=node('article',undefined,'basket-row');
              var vr=viewsRow(lineViews(at));if(vr)row.append(vr);
              var meta=node('div',undefined,'basket-meta');
              meta.append(node('h2',((n.merchandise||{}).title)||'Card'),node('p','Qty '+qty),node('strong','£'+(unit*qty).toFixed(2)));
              row.append(meta);
              var step=node('div',undefined,'basket-step'),lineId=n.id;
              [['−',qty-1],['+',qty+1]].forEach(function(q){
                var qb=node('button',q[0],'oc-button');qb.type='button';
                if(q[1]<1)qb.disabled=true;
                else qb.onclick=function(){qb.disabled=true;host.post('/cart/lines',{cart_id:cid,action:'update',line_id:lineId,qty:q[1]}).then(function(){cart();}).catch(function(err){qb.disabled=false;body.append(node('p',err.message));});};
                step.append(qb);
              });
              var rm=node('button','Remove','oc-button');rm.type='button';
              rm.onclick=function(){rm.disabled=true;host.post('/cart/lines',{cart_id:cid,action:'remove',line_id:lineId}).then(function(){cart();}).catch(function(err){body.append(node('p',err.message));cart();});};
              step.append(rm);row.append(step);body.append(row);
            });
            if(edges.length){
              var sum=node('div',undefined,'basket-summary');
              sum.append(node('p',shopCount+' item'+(shopCount===1?'':'s')+' · subtotal £'+shopTotal.toFixed(2)+' · shipping calculated at checkout'));
              if(shopCheckout){var co=node('a','Checkout · £'+shopTotal.toFixed(2),'oc-button');co.href=shopCheckout;sum.append(co);}
              body.append(sum);
            }
          }catch(e){cid=null;}
        }
        // ── 2. reservations (local rows with their own invoice links) ──
        var result=await host.get('/studio/basket');if(ticket!==cartGeneration)return;
        var res=(result.items||[]);
        if(res.length)body.append(node('h2','Reserved'));
        res.forEach(function(item){
          var qty=Math.max(1,parseInt(item.qty||1,10)||1);count+=qty;
          var row=node('article',undefined,'basket-row');
          var vr=viewsRow(item.views||[]);if(vr)row.append(vr);
          else if(item.preview){var pim=node('img');pim.alt=item.label;pim.loading='lazy';pim.src=host.asset(item.preview);pim.onerror=function(){pim.remove();};row.append(pim);}
          var meta=node('div',undefined,'basket-meta');
          meta.append(node('h2',item.label),node('p',qty+' × '+String(item.status||'pending_checkout').replaceAll('_',' ')),node('strong',money((item.price_cents||0)*qty)));
          row.append(meta);
          if(item.checkout_url){var co2=node('a','Pay · '+money(item.price_cents),'oc-button');co2.href=item.checkout_url;row.append(co2);}
          else if(item.kind==='card'&&item.design_id)row.append(link('Open card','/cards/'+item.design_id));
          body.append(row);
        });
        // ── 3. saved creations ──
        var drafts=(result.drafts||[]).filter(function(d){return !res.some(function(i){return i.design_id===d.design_id;});});
        if(drafts.length){
          body.append(node('h2','Saved creations'));
          drafts.forEach(function(d){
            var row=node('article',undefined,'basket-row');
            var vr=viewsRow(d.views||[]);if(vr)row.append(vr);
            else if(d.preview){var dim=node('img');dim.alt=d.label;dim.loading='lazy';dim.src=host.asset(d.preview);dim.onerror=function(){dim.remove();};row.append(dim);}
            row.append(node('h2',d.label),node('p','Draft · revision '+d.revision));
            if(d.export_ready){var b=node('button','Add to basket','oc-button');b.type='button';b.onclick=function(){b.disabled=true;host.post('/cart/create',{design_id:d.design_id,revision:d.revision,qty:1}).then(function(c){try{localStorage.setItem('oddhobb.cartId',((c.cart||{}).id)||'');}catch(e){}cart();}).catch(function(e){b.disabled=false;body.append(node('p',e.message));});};row.append(b);}
            else row.append(link('Finish in studio','/cards/'+d.design_id));
            body.append(row);
          });
        }
        setBadge(shopCount+count);
        if(!res.length&&!drafts.length&&!shopCount)body.append(node('p','Your basket is empty. Choose a card or personalised product to get started.'));
        body.append(link('Browse products','/products'),link('Greeting cards','/cards'));
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
