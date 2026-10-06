(function(){
  'use strict';
  function node(tag,text,cls){var n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
  function link(text,path){var a=node('a',text,'oc-button');a.href=path;a.dataset.route='';return a;}
  window.OddHobbShell=function(host){
    var accountDialog=node('dialog',undefined,'studio-dialog');accountDialog.id='account-dialog';
    var inner=node('div',undefined,'studio-dialog-inner'),close=node('button','Close','studio-dialog-close');close.type='button';close.onclick=function(){accountDialog.close();};
    inner.append(close,node('h2','Your OddHobb account'),node('p','Sign in to keep your friends, photos and saved designs together.'));
    ['g-signin','g-who'].forEach(function(id){var n=document.getElementById(id);if(n)inner.append(n);});
    inner.append(link('Account and orders','/account'));accountDialog.append(inner);document.body.append(accountDialog);
    var accountPanel=document.getElementById('panel-account');accountPanel.querySelector('.panel__inner').append(node('h1','Your account'),node('p','Your photos and creations stay with your account.'),link('View basket','/cart'));
    var sign=node('button','Sign in','oc-button');sign.type='button';sign.onclick=openAccount;accountPanel.querySelector('.panel__inner').append(sign);
    function openAccount(){if(!accountDialog.open)accountDialog.showModal();}
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
    async function cart(){
      var ticket=++cartGeneration,body=document.querySelector('#panel-cart .panel__inner');body.replaceChildren(node('h1','Your basket'),node('p','Loading your saved reservations…'));
      try{await host.ready();var result=await host.get('/studio/basket');if(ticket!==cartGeneration)return;body.replaceChildren(node('h1','Your basket'));
        var total=0;result.items.forEach(function(item){var row=node('article',undefined,'basket-row');row.append(node('h2',item.label),node('p',item.qty+' × '+item.status.replaceAll('_',' ')),node('strong','£'+(item.price_cents/100).toFixed(2)));if(item.design_id)row.append(link('Open card','/cards/'+item.design_id));body.append(row);total+=item.price_cents;});
        document.getElementById('cart-n').textContent=String(result.items.length);
        if(result.items.length)body.append(node('p','Reserved items: £'+(total/100).toFixed(2)+'. Shipping is quoted separately.'));
        else body.append(node('p','Your basket is empty. Choose a card or personalised product to get started.'));
        body.append(link('Browse products','/products'),link('Greeting cards','/cards'));
        if(result.items.length)body.append(node('p','These are reservations; you have not been charged. Checkout links appear only when a supplier quote is available.'));
        result.items.filter(function(i){return i.checkout_url;}).forEach(function(i){var a=node('a','Checkout '+i.label,'oc-button');a.href=i.checkout_url;body.append(a);});
      }catch(e){body.replaceChildren(node('h1','Your basket'),node('p',e.message));}
    }
    return {openAccount:openAccount,search:search,cart:cart};
  };
})();
