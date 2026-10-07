(function(){
  "use strict";
  function el(tag,text,cls){var n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;}
  function btn(text,fn,cls){var b=el("button",text,cls||"oc-button");b.type="button";b.onclick=fn;return b;}
  function firstConfirmedPhoto(ctx){
    if(!ctx||!ctx.subject)return "";
    var photos=ctx.photos||[];
    for(var i=0;i<photos.length;i++){
      var p=photos[i],links=p.subjects||[];
      if(links.some(function(l){return l.subject_id===ctx.subject.id&&l.confirmed;}))return p.id;
    }
    return photos[0]&&photos[0].id||"";
  }
  function art(t){
    var a=el("div",null,"oc-vt-art");a.dataset.style=t.style||"generic";
    a.append(el("span",(t.style||"template").replace(/_/g," "),"oc-vt-style"),
             el("strong",t.label||t.id,"oc-vt-name"));
    var ghost=el("div",null,"oc-vt-ghost");
    ghost.append(el("i"),el("i"),el("i"));a.append(ghost);return a;
  }
  async function instantiate(t,host,msg){
    var ctx=window.OddHobbStudioContext||{},subject=ctx.subject||{},sid=subject.id||"";
    if((t.requirements||{}).subjects&&!sid){
      msg.textContent="Pick Dad, Mum, a friend or a pet in Studio first.";return;
    }
    var fields={};
    Object.keys(t.slots||{}).forEach(function(k){
      var s=t.slots[k]||{};
      if(s.type==="text"&&s.default!=null)fields[k]=s.default;
      if(s.type==="subject"&&sid)fields[k]=sid;
    });
    msg.textContent="Building a first remix…";
    try{
      await host.ready();
      var project=await host.post("/creative/projects",{subject_id:sid,template_id:t.id});
      var photo=firstConfirmedPhoto(ctx);
      var subjects=sid?[{slot:"star",subject_id:sid,asset_ids:photo?[photo]:[]}]:[];
      var saved=await host.post("/creative/revisions",{
        project_id:project.project.id,template_id:t.id,subject_id:sid,
        fields:fields,subjects:subjects,
        render_intent:{style:t.style,occasion:(t.occasion||[])[0]||"general"}
      });
      var rev=saved.revision.revision;
      var rendered=await host.post("/creative/render",{project_id:project.project.id,revision:rev});
      msg.replaceChildren(document.createTextNode("Saved remix · r"+rev+" "));
      var u=rendered.artifact&&rendered.artifact.url;
      if(u){
        var href=/^https?:/i.test(u)?u:host.asset(u);
        var link=el("a","Open preview","oc-button");link.href=href;link.target="_blank";link.rel="noopener";
        msg.append(link);
      }
    }catch(e){msg.textContent=e.message||String(e);}
  }
  window.OddHobbViralCards={
    mount:function(panel,host){
      if(!panel||panel.querySelector(".oc-viral-library"))return;
      var root=el("section",null,"oc-viral-library");
      var intro=el("div",null,"oc-viral-head");
      intro.append(el("h2","Pick a format, not a blank card"),
        el("p","Viral joke formats, remixed around your people. Same template can become a printed card now and a talking clip later."));
      var filters=el("div",null,"oc-viral-filters"),rails=el("div",null,"oc-viral-rails");
      root.append(intro,filters,rails);panel.insertBefore(root,panel.firstChild);
      var cat=null,occasion="all";
      var filterDefs=[["For you","all"],["Christmas","christmas"],["Birthday","birthday"],["Father's Day","fathers_day"],["Mother's Day","mothers_day"],["Retirement","retirement"]];
      function paintFilters(){
        filters.replaceChildren();
        filterDefs.forEach(function(x){
          filters.append(btn(x[0],function(){occasion=x[1];paintFilters();paint();},
            "oc-viral-chip"+(occasion===x[1]?" selected":"")));
        });
      }
      function tile(t){
        var card=el("article",null,"oc-vt");
        card.append(art(t));
        var copy=el("div",null,"oc-vt-copy");
        copy.append(el("p",t.premise||"","oc-vt-premise"),
                    el("p","“"+(t.example_caption||"")+"”","oc-vt-example"));
        var msg=el("div","", "oc-vt-result");
        copy.append(btn("Use this idea",function(){instantiate(t,host,msg);},"oc-button"),msg);
        card.append(copy);return card;
      }
      function paint(){
        if(!cat)return;
        rails.replaceChildren();
        var items=(cat.templates||[]).filter(function(t){
          return occasion==="all"||(t.occasion||[]).indexOf(occasion)>=0;
        });
        (cat.styles||[]).forEach(function(st){
          var mine=items.filter(function(t){return t.style===st.id;});
          if(!mine.length)return;
          var sec=el("section",null,"oc-vt-family"),head=el("div",null,"oc-vt-family-head");
          head.append(el("h3",st.label),el("p",st.description||""));
          var rail=el("div",null,"oc-vt-rail");
          mine.forEach(function(t){rail.append(tile(t));});
          sec.append(head,rail);rails.append(sec);
        });
        if(!rails.children.length)rails.append(el("p","Nothing in this filter yet.","oc-viral-empty"));
      }
      paintFilters();
      host.get("/creative/catalog").then(function(d){cat=d;paint();})
        .catch(function(e){rails.append(el("p","Template library unavailable: "+e.message,"oc-viral-empty"));});
    }
  };
})();
