/* CARD P0 — finished buyable cards, nothing else.
 * select/upload a person → finished personalised cards → Front/Inside/Back → Buy.
 * No formats, no premises, no "Use this idea", no Motion, no Reserve.
 * Every tile is the actual rendered FRONT of a saved immutable revision.
 */
(function () {
  "use strict";

  function el(tag, text, cls) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function money(c) {
    return "£" + (c / 100).toFixed(2);
  }

  window.OddHobbGallery = {
    mount: function (panelInner, host) {
      var wrap = el("div", null, "oc-gallery");
      var head = el("div", null, "oc-gallery__head");
      var title = el("h3", "Cards for you");
      var sub = el("p", "Finished cards with their photos — tap one to inspect Front / Inside / Back, then buy.");
      var occRow = el("div", null, "oc-gallery__occ");
      head.append(title, sub, occRow);
      var grid = el("div", null, "oc-gallery__grid");
      wrap.append(head, grid);
      panelInner.insertBefore(wrap, panelInner.firstChild);

      var subjectId = "", subjectName = "", selectedIds = [];
      var occasion = "birthday";

      function personLabel() {
        if (subjectName) return subjectName.split(" ")[0];
        var ctx = window.OddHobbStudioContext || {};
        if (ctx.subject && ctx.subject.name) return String(ctx.subject.name).split(" ")[0];
        return "you";
      }
      function paintHead(n) {
        if (n) title.textContent = "Cards for " + n;
        else title.textContent = "Cards for " + personLabel();
      }
      function paintOcc() {
        occRow.replaceChildren();
        [["Birthday", "birthday"], ["Christmas", "christmas"]].forEach(function (pair) {
          var b = el("button", pair[0], "oc-button" + (occasion === pair[1] ? " selected" : ""));
          b.type = "button";
          b.onclick = function () { occasion = pair[1]; paintOcc(); load(); };
          occRow.appendChild(b);
        });
      }
      function galleryUrl() {
        var u = "/cards/gallery";
        var q = [];
        if (subjectId) q.push("subject_id=" + encodeURIComponent(subjectId));
        if (occasion) q.push("occasion=" + encodeURIComponent(occasion));
        if (selectedIds.length) q.push("photo_ids=" + encodeURIComponent(selectedIds.join(",")));
        return q.length ? u + "?" + q.join("&") : u;
      }
      function syncCtx(ctx) {
        ctx = ctx || window.OddHobbStudioContext || {};
        var sid = (ctx.subject && ctx.subject.id) || "";
        var nm = (ctx.subject && ctx.subject.name) || "";
        var changed = false;
        if (sid !== subjectId) { subjectId = sid; changed = true; }
        if (nm && nm !== subjectName) { subjectName = nm; paintHead(nm.split(" ")[0] === nm ? nm : nm); changed = true; }
        if (!nm && !subjectName && ctx.subject) paintHead();
        return changed;
      }
      document.addEventListener("oddhobb:subject", function (e) {
        var ctx = (e && e.detail) || window.OddHobbStudioContext || {};
        var sid = (ctx.subject && ctx.subject.id) || "";
        var nm = (ctx.subject && ctx.subject.name) || "";
        subjectId = sid; subjectName = nm || "";
        paintHead(); load();
      });
      document.addEventListener("oddhobb:card-photos", function (e) {
        selectedIds = (((e && e.detail && e.detail.photo_ids) || []).slice(0, 8));
        load();
      });

      function tile(item) {
        var card = el("div", null, "oc-card");
        var frame = el("div", null, "oc-card__frame");
        var img = el("img");
        img.alt = item.headline || "Finished card";
        img.loading = "lazy";
        frame.append(img);
        var status = el("div", null, "oc-card__status");
        frame.append(status);
        card.append(frame);
        var body = el("div", null, "oc-card__body");
        body.append(el("div", item.headline, "oc-card__headline"));
        body.append(el("div", money(item.price_cents), "oc-card__meta"));
        var bar = el("div", null, "oc-toolbar");
        var viewBtn = el("button", "View card", "oc-button");
        var photosBtn = el("button", "Different photos", "oc-button");
        var buyBtn = el("button", "Buy · " + money(item.price_cents), "oc-button");
        var shipSel = document.createElement("select");
        shipSel.className = "oc-button";
        shipSel.setAttribute("aria-label", "Delivery country");
        [["GB", "UK delivery"], ["US", "US delivery"]].forEach(function (o) {
          var op = document.createElement("option");
          op.value = o[0]; op.textContent = o[1];
          shipSel.appendChild(op);
        });
        try { shipSel.value = localStorage.getItem("oddhobb.country") || "GB"; } catch (e) {}
        if (shipSel.value !== "GB" && shipSel.value !== "US") shipSel.value = "GB";
        shipSel.onchange = function () {
          try { localStorage.setItem("oddhobb.country", shipSel.value); } catch (e) {}
        };
        bar.append(viewBtn, photosBtn, buyBtn, shipSel);
        body.append(bar);
        var msg = el("div", null, "oc-card__msg");
        body.append(msg);
        card.append(body);

        var pollTimer = null;
        function showPreview(url) {
          img.src = host.asset(url);
          status.textContent = "";
          if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
        }
        img.onerror = function () {
          if (item.photo && item.photo.url && img.getAttribute("src") !== host.asset(item.photo.url)) {
            img.src = host.asset(item.photo.url);
          }
        };
        function pollPreview() {
          status.textContent = "finishing this card…";
          var tries = 0;
          if (pollTimer) clearInterval(pollTimer);
          pollTimer = setInterval(function () {
            if (++tries > 20) { clearInterval(pollTimer); status.textContent = "still working — tap View card again"; return; }
            host.get(galleryUrl()).then(function (g) {
              var fresh = (g.items || []).filter(function (x) { return x.design_id === item.design_id; })[0];
              if (fresh && fresh.preview_url) { item.preview_url = fresh.preview_url; showPreview(fresh.preview_url); }
            }).catch(function () {});
          }, 4000);
        }
        if (item.preview_url) showPreview(item.preview_url);
        else {
          if (item.photo && item.photo.url) img.src = host.asset(item.photo.url);
          host.post("/cards/" + item.design_id + "/render",
            { revision: item.revision, kind: "preview" }).catch(function () {});
          pollPreview();
        }
        function openDetail() { detail(item, msg); }
        viewBtn.onclick = openDetail;
        img.style.cursor = "pointer";
        img.onclick = openDetail;
        photosBtn.onclick = function () {
          msg.textContent = "Finding different photos…";
          host.post("/cards/" + item.design_id + "/reroll",
            { revision: item.revision, subject_id: subjectId })
            .then(function () { msg.textContent = "New card below."; load(); })
            .catch(function (e) { msg.textContent = e.message || String(e); });
        };
        buyBtn.onclick = function () { buy(item, msg); };
        return card;
      }

      function detail(item, msg) {
        var overlay = el("div", null, "oc-carddetail");
        var box = el("div", null, "oc-carddetail__box");
        var who = item.recipient || personLabel();
        box.append(el("h3", (who ? who + "'s " : "") + "Card"));
        box.append(el("p", money(item.price_cents)));
        var faces = el("div", null, "oc-carddetail__faces");
        var labels = [["front", "FRONT"], ["inside", "INSIDE"], ["back", "BACK"]];
        var imgs = {};
        labels.forEach(function (pair) {
          var fig = el("figure", null, "oc-face");
          var im = el("img");
          im.alt = pair[1];
          im.loading = "lazy";
          var src = (item.views && item.views[pair[0]]) ||
            ("/cards/" + item.design_id + "/r" + item.revision + "/" + pair[0]);
          im.src = host.asset(src);
          fig.append(el("figcaption", pair[1]), im);
          faces.append(fig);
          imgs[pair[0]] = im;
        });
        box.append(faces);
        box.append(el("p", '"' + (item.headline || "") + '"', "oc-carddetail__headline"));
        var bar = el("div", null, "oc-toolbar");
        var changeBtn = el("button", "Change wording", "oc-button");
        var photosBtn = el("button", "Different photos", "oc-button");
        var buyBtn = el("button", "Buy this card · " + money(item.price_cents), "oc-button");
        var closeBtn = el("button", "Close", "oc-button");
        bar.append(changeBtn, photosBtn, buyBtn, closeBtn);
        box.append(bar);
        var dmsg = el("div", null, "oc-card__msg");
        box.append(dmsg);
        overlay.append(box);
        document.body.appendChild(overlay);
        closeBtn.onclick = function () { overlay.remove(); };
        overlay.addEventListener("click", function (e) { if (e.target === overlay) overlay.remove(); });
        // Ensure all three faces exist; queue renders if any 409s.
        ["preview", "spread"].forEach(function (kind) {
          host.post("/cards/" + item.design_id + "/render",
            { revision: item.revision, kind: kind }).catch(function () {});
        });
        changeBtn.onclick = function () {
          dmsg.textContent = "";
          host.get("/cards/designs/" + item.design_id).then(function (d) {
            var spec = (d.design && d.design.spec) || null;
            if (!spec) throw new Error("Could not open this card.");
            var rev = (d.design && d.design.revision) || item.revision;
            var next = window.prompt("Inside message", spec.inside_message || "");
            if (next === null) return null;
            next = String(next).slice(0, 240);
            return host.post("/cards/designs",
              { id: item.design_id, expected_revision: rev, via: "ui",
                spec: Object.assign({}, spec, { inside_message: next }) });
          }).then(function (d) {
            if (!d) return;
            item.revision = d.design.revision;
            dmsg.textContent = "Saved — new Front / Inside / Back rendering…";
            return host.post("/cards/" + item.design_id + "/render",
              { revision: item.revision, kind: "preview" });
          }).then(function () { load(); overlay.remove(); })
            .catch(function (e) { dmsg.textContent = e.message || String(e); });
        };
        photosBtn.onclick = function () {
          dmsg.textContent = "Finding different photos…";
          host.post("/cards/" + item.design_id + "/reroll",
            { revision: item.revision, subject_id: subjectId })
            .then(function () { overlay.remove(); load(); })
            .catch(function (e) { dmsg.textContent = e.message || String(e); });
        };
        buyBtn.onclick = function () { buy(item, dmsg); };
      }

      function buy(item, msg) {
        msg.textContent = "Preparing print artwork, then delivery options…";
        var country = "GB";
        try { country = localStorage.getItem("oddhobb.country") || "GB"; } catch (e) {}
        if (country !== "GB" && country !== "US") country = "GB";
        host.post("/cards/" + item.design_id + "/render",
          { revision: item.revision, kind: "export" })
          .then(function () { return waitForExport(item, 0); })
          .then(function () {
            return host.get("/cards/" + item.design_id + "/delivery?revision=" +
              item.revision + "&country=" + encodeURIComponent(country)).catch(function () { return null; });
          })
          .then(function (d) {
            if (!d || !d.ok || !d.value) return {};
            return pickDelivery(msg, d);
          })
          .then(function (pick) {
            var cid = null;
            try { cid = localStorage.getItem("oddhobb.cartId"); } catch (e) { cid = null; }
            if (cid) {
              var body = { revision: item.revision, qty: 1, cart_id: cid, action: "add", design_id: item.design_id };
              if (pick && pick.id) body.delivery_option_id = pick.id;
              return host.post("/cart/lines", body).catch(function () { return null; })
                .then(function (dd) {
                  if (dd) return dd;
                  var b2 = { design_id: item.design_id, revision: item.revision, qty: 1 };
                  if (pick && pick.id) b2.delivery_option_id = pick.id;
                  return host.post("/cart/create", b2).then(function (d2) {
                    try { localStorage.setItem("oddhobb.cartId", ((d2.cart || {}).id) || ""); } catch (e) {}
                    return d2;
                  });
                });
            }
            var b3 = { design_id: item.design_id, revision: item.revision, qty: 1 };
            if (pick && pick.id) b3.delivery_option_id = pick.id;
            return host.post("/cart/create", b3).then(function (d3) {
              try { localStorage.setItem("oddhobb.cartId", ((d3.cart || {}).id) || ""); } catch (e) {}
              return d3;
            });
          })
          .then(function () {
            msg.textContent = "In your basket — taking you there…";
            location.href = "/cart";
          })
          .catch(function (e) { msg.textContent = e.message || String(e); });
      }
      function pickDelivery(msg, d) {
        return new Promise(function (resolve) {
          var wrap = document.createElement("div");
          function fmtOpt(o) {
            return o.label + " · £" + (o.price_cents / 100).toFixed(2) +
              " · arrives " + o.arrival_from + " – " + o.arrival_to;
          }
          [["value", d.value], ["speedy", d.speedy]].forEach(function (pair) {
            var o = pair[1];
            if (!o || !o.id) return;
            var b = document.createElement("button");
            b.type = "button"; b.className = "oc-button"; b.textContent = fmtOpt(o);
            b.onclick = function () { wrap.remove(); resolve(o); };
            wrap.appendChild(b);
          });
          if (!wrap.children.length) { resolve({}); return; }
          var cancel = document.createElement("button");
          cancel.type = "button"; cancel.className = "oc-button";
          cancel.textContent = "Standard shipping";
          cancel.onclick = function () { wrap.remove(); resolve({}); };
          wrap.appendChild(cancel);
          msg.textContent = "Choose delivery — estimated arrival:";
          msg.appendChild(wrap);
        });
      }
      function waitForExport(item, tries) {
        return host.get("/cards/" + item.design_id + "/scene?revision=" + item.revision)
          .then(function (s) {
            var st = (((s || {}).scene || {}).outputs || {}).export || {};
            if (st.status === "ready") return true;
            if (st.status === "failed") throw new Error(st.error || "Export failed.");
            if (tries > 25) throw new Error("Still building artwork — tap Buy again.");
            return new Promise(function (res) { setTimeout(res, 3000); })
              .then(function () { return waitForExport(item, tries + 1); });
          });
      }

      function load() {
        var ctx = window.OddHobbStudioContext || {};
        if (ctx.subject && ctx.subject.id) {
          subjectId = ctx.subject.id;
          subjectName = ctx.subject.name || subjectName;
        }
        paintHead();
        host.get(galleryUrl()).then(function (g) {
          grid.replaceChildren();
          if (!g.items || !g.items.length) {
            var who = personLabel();
            grid.append(el("p",
              occasion === "christmas"
                ? "No Christmas cards yet for " + who + " — try Birthday."
                : "No confirmed photos for " + who + " yet — tag them in Studio and cards appear here.",
              "oc-empty"));
            return;
          }
          g.items.forEach(function (item) { grid.append(tile(item)); });
        }).catch(function () {
          grid.append(el("p", "Gallery unavailable — the studio below still works.", "oc-empty"));
        });
      }
      paintHead();
      paintOcc();
      load();
      document.addEventListener("oddhobb:route", function () { syncCtx(); load(); });
    }
  };
})();
