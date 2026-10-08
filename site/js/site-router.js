/* One URL resolver for initial load, internal links and browser history. */
(function (root) {
  'use strict';
  var paths = {quick:'/',studio:'/studio',products:'/products',cards:'/cards',videos:'/videos',perform:'/perform',funnier:'/funnier',art:'/art',search:'/search',cart:'/cart',account:'/account'};
  function resolve(input) {
    var u = new URL(input, 'https://oddhobb.com');
    var hash = u.hash.slice(1), p = u.pathname.replace(/\/$/, '') || '/';
    if (hash && p === '/') {
      if (/^\/s\//.test(hash)) {
        var section = hash.slice(3);
        p = section === 'cards' ? '/cards' : section === 'my' ? '/studio' : '/products';
        if (!['cards','my','all'].includes(section)) u.searchParams.set('section',section);
      } else if (hash === 'upload') p='/studio';
      else if (paths[hash]) p=paths[hash];
      else if (hash==='chat') p='/';
    }
    if (p==='/index.html') p='/';
    if (p==='/upload') p='/studio';
    if (p==='/shop') p='/products';
    var m=p.match(/^\/studio\/people\/([\w-]+)$/);
    if (m) return {tab:'studio',subjectId:m[1],path:p+u.search};
    m=p.match(/^\/(cards|videos|products)\/([\w-]+)$/);
    if (m) return {tab:m[1],id:m[2],path:p+u.search};
    var tab=Object.keys(paths).find(function(k){return paths[k]===p;});
    return {tab:tab||'notfound',path:p+u.search,q:u.searchParams.get('q')||'',section:u.searchParams.get('section')||''};
  }
  var api={resolve:resolve,paths:paths,current:null};
  if (typeof module!=='undefined') module.exports=api;
  if (!root.document) return;
  var render=null;
  api.pathFor=function(tab){return paths[tab==='upload'?'studio':tab==='shop'?'products':tab==='chat'?'quick':tab]||'/';};
  api.navigate=function(path,options){
    options=options||{}; var route=resolve(path);
    if (api.current && route.path!==api.current.path) {
      document.dispatchEvent(new CustomEvent('oddhobb:before-route',{detail:route}));
    }
    var previous=api.current;
    if (!options.history) {
      if (options.replace) history.replaceState({path:route.path},'',route.path);
      else if (location.pathname+location.search!==route.path || location.hash) history.pushState({path:route.path},'',route.path);
    }
    api.current=route;
    document.querySelectorAll('#tabrail [data-tab]').forEach(function(a){
      var active=a.dataset.tab===route.tab;
      a.classList.toggle('active',active);
      if(active) a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');
    });
    document.title=(route.tab==='quick'?'Find an odd gift':route.tab==='notfound'?'Page not found':route.tab.charAt(0).toUpperCase()+route.tab.slice(1))+' · OddHobb';
    if(render) render(route,previous);
    document.dispatchEvent(new CustomEvent('oddhobb:route',{detail:route}));
  };
  api.start=function(fn){render=fn;api.navigate(location.href,{replace:true});};
  document.addEventListener('click',function(e){
    var a=e.target.closest('a[data-route]');
    if(!a||e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey) return;
    e.preventDefault();api.navigate(a.getAttribute('href'));
  });
  window.addEventListener('popstate',function(){api.navigate(location.href,{history:true});});
  window.addEventListener('hashchange',function(){if(location.hash)api.navigate(location.href,{replace:true});});
  root.OddHobbRouter=api;
})(typeof window==='undefined'?globalThis:window);
