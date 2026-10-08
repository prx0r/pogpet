/* Art shelf: browse the art, pick a surface. Postcard / card / mug /
 * poster / live MP4. No photo, no mesh, no credits.
 * Usage: window.OddHobbArt({get, post, asset}).open()
 */
(function () {
  "use strict";
  function el(tag, text, cls) {
    var n = document.createElement(tag);
    if (text !== undefined && text !== null) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  }
  function money(c) { return "£" + (c / 100).toFixed(2).replace(/\.00$/, ""); }
  window.OddHobbArt = function (host) {
    var mount = document.getElementById("art-mount");
    var grid = el("div", null, "oc-art-grid");
    var sheet = el("div", null, "oc-art-sheet");
    var msg = el("p", "", "panel__msg");
    msg.setAttribute("role", "status");
    var formats = {};
    function tile(item) {
      var card = el("article", null, "oc-art-tile");
      card.append(el("h3", item.title, "oc-art-title"));
      card.append(el("p", item.premise || "", "oc-art-premise"));
      card.append(el("p", "“" + (item.caption || "") + "”", "oc-art-caption"));
      var btn = el("button", "Put it on something →", "btn");
      btn.type = "button";
      btn.addEventListener("click", function () { openSheet(item); });
      card.append(btn);
      return card;
    }
    function openSheet(item) {
      sheet.replaceChildren();
      sheet.append(el("h3", item.title, "oc-art-title"));
      Object.keys(formats).forEach(function (key) {
        var f = formats[key];
        var row = el("div", null, "oc-art-row");
        row.append(el("div", f.label + " · " + money(f.price_cents), "oc-art-format"));
        row.append(el("div", f.blurb || "", "panel__fine"));
        var go = el("button", key === "mp4" ? "Make it a video →" : "Buy " + money(f.price_cents) + " →", "btn ghost");
        go.type = "button";
        go.addEventListener("click", function () { buy(item, key); });
        row.append(go);
        sheet.append(row);
      });
      sheet.scrollIntoView({block: "start"});
    }
    function buy(item, format) {
      msg.textContent = format === "mp4" ? "Rendering your video…" : "Reserving…";
      var done = function (text) { msg.textContent = text; };
      if (format === "mp4") {
        host.post("/creative/art/mp4", {art_id: item.id}).then(function (d) {
          var a = el("a", "Download MP4", "btn");
          a.href = host.asset(d.mp4_url); a.download = item.id + ".mp4";
          msg.replaceChildren(document.createTextNode("Your video is ready. "), a);
        }).catch(function (e) { done(e.message || String(e)); });
        return;
      }
      host.post("/creative/art/order", {art_id: item.id, format: format, qty: 1}).then(function (d) {
        var o = d.order || {};
        done("Reserved · " + money(o.price_cents || 0) + " estimate · no payment taken. " +
          (d.draft_url ? "Checkout: " + d.draft_url : "Order " + (o.id || "")));
      }).catch(function (e) { done(e.message || String(e)); });
    }
    return {
      open: function () {
        if (!mount) return;
        if (!mount.querySelector(".oc-art-grid")) mount.append(grid, sheet, msg);
        if (grid.children.length) return;
        msg.textContent = "Hanging the gallery…";
        host.get("/creative/art").then(function (d) {
          formats = d.formats || {};
          msg.textContent = "";
          (d.items || []).forEach(function (item) { grid.append(tile(item)); });
          if (!grid.children.length) msg.textContent = "Nothing hung yet. Check back soon.";
        }).catch(function (e) { msg.textContent = e.message || String(e); });
      }
    };
  };
})();
