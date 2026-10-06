/* Ready-made card gallery: your photos, already composed. No forms.
 * Mounts above the studio editor. Previews render lazily server-side;
 * pending tiles poll until their preview lands. Reserve + Motion per card.
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
    return "£" + (c / 100).toFixed(2).replace(/\.00$/, "");
  }

  window.OddHobbGallery = {
    mount: function (panelInner, host) {
      var wrap = el("div", null, "oc-gallery");
      var head = el("div", null, "oc-gallery__head");
      head.append(el("h3", "Ready-made, with your photos"));
      head.append(el("p", "Composed from your uploads the moment they land. Tap to preview, reserve, or play the motion version. The studio below is for tinkerers."));
      var grid = el("div", null, "oc-gallery__grid");
      wrap.append(head, grid);
      panelInner.insertBefore(wrap, panelInner.firstChild);

      function tile(item) {
        var card = el("div", null, "oc-card");
        var frame = el("div", null, "oc-card__frame");
        var img = el("img");
        img.alt = item.headline;
        img.loading = "lazy";
        frame.append(img);
        var status = el("div", null, "oc-card__status");
        frame.append(status);
        card.append(frame);
        var body = el("div", null, "oc-card__body");
        body.append(el("div", item.headline, "oc-card__headline"));
        if (item.recipient) body.append(el("div", "for " + item.recipient, "oc-card__to"));
        body.append(el("div", item.template_label + " · " + money(item.price_cents), "oc-card__meta"));
        var bar = el("div", null, "oc-toolbar");
        var prevBtn = el("button", "Preview", "oc-button");
        var motBtn = el("button", "Motion", "oc-button");
        var ordBtn = el("button", "Reserve " + money(item.price_cents), "oc-button");
        bar.append(prevBtn, motBtn, ordBtn);
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
        function pollPreview() {
          status.textContent = "rendering preview…";
          var tries = 0;
          pollTimer = setInterval(function () {
            if (++tries > 20) { clearInterval(pollTimer); status.textContent = "still working — tap Preview again"; return; }
            host.get("/cards/designs/" + item.design_id).then(function () {
              return host.post("/cards/" + item.design_id + "/render",
                { revision: item.revision, kind: "preview" }).catch(function () { return null; });
            }).then(function () {
              return host.get("/cards/gallery");
            }).then(function (g) {
              var fresh = (g.items || []).filter(function (x) { return x.design_id === item.design_id; })[0];
              if (fresh && fresh.preview_url) { item.preview_url = fresh.preview_url; showPreview(fresh.preview_url); }
            }).catch(function () {});
          }, 4000);
        }
        if (item.preview_url) showPreview(item.preview_url);
        else {
          img.src = host.asset(item.photo.url);
          pollPreview();
        }
        prevBtn.onclick = function () {
          msg.textContent = "";
          host.post("/cards/" + item.design_id + "/render",
            { revision: item.revision, kind: "preview" })
            .then(function () { pollPreview(); })
            .catch(function (e) { msg.textContent = e.message || String(e); });
        };
        motBtn.onclick = function () {
          msg.textContent = "making the motion version…";
          host.post("/cards/" + item.design_id + "/render",
            { revision: item.revision, kind: "motion" })
            .then(function () { msg.textContent = "Motion rendering — check Videos shortly."; })
            .catch(function (e) { msg.textContent = e.message || String(e); });
        };
        ordBtn.onclick = function () {
          msg.textContent = "Preparing print artwork, then reserving…";
          var key = "g-" + item.design_id + "-r" + item.revision + "-" + Date.now().toString(36);
          // Reserve requires export-ready artwork: build it first, poll it,
          // then place the idempotent order.
          host.post("/cards/" + item.design_id + "/render",
            { revision: item.revision, kind: "export" })
            .then(function () { return waitForExport(0); })
            .then(function () {
              return host.post("/cards/" + item.design_id + "/order",
                { revision: item.revision, qty: 1, idempotency_key: key });
            })
            .then(function (d) {
              msg.textContent = "Reserved" + (d.order && d.order.id ? " · " + d.order.id : "") + ". No charge — supplier checkout connects next.";
              try { var b = document.getElementById('cart-n'); if (b) b.textContent = String((parseInt(b.textContent || '0', 10) || 0) + 1); } catch (e) {}
            })
            .catch(function (e) { msg.textContent = e.message || String(e); });
        };
        function waitForExport(tries) {
          return host.get("/cards/" + item.design_id + "/scene?revision=" + item.revision)
            .then(function (s) {
              var st = (((s || {}).scene || {}).outputs || {}).export || {};
              if (st.status === "ready") return true;
              if (st.status === "failed") throw new Error(st.error || "Export failed.");
              if (tries > 25) throw new Error("Still building artwork — tap Reserve again.");
              return new Promise(function (res) { setTimeout(res, 3000); })
                .then(function () { return waitForExport(tries + 1); });
            });
        }
        return card;
      }

      host.get("/cards/gallery").then(function (g) {
        grid.replaceChildren();
        if (!g.items || !g.items.length) {
          grid.append(el("p", "Upload a photo and your ready-made cards appear here.", "oc-empty"));
          return;
        }
        g.items.forEach(function (item) { grid.append(tile(item)); });
      }).catch(function () {
        grid.append(el("p", "Gallery unavailable — the studio below still works.", "oc-empty"));
      });
    }
  };
})();
