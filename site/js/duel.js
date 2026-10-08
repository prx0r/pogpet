/* Funnier: two comics enter, one leaves. Every vote trains the humour model.
 * Usage: window.OddHobbDuel({get, post}).open() on #panel-funnier.
 */
(function () {
  "use strict";
  function el(tag, text, cls) {
    var n = document.createElement(tag);
    if (text !== undefined && text !== null) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  }
  function count() {
    try { return parseInt(localStorage.getItem("oddhobb.duels") || "0", 10) || 0; }
    catch (e) { return 0; }
  }
  function bump() {
    try { localStorage.setItem("oddhobb.duels", String(count() + 1)); } catch (e) {}
  }
  window.OddHobbDuel = function (host) {
    var mount = document.getElementById("duel-mount");
    var score = el("p", "", "panel__fine");
    var arena = el("div", null, "oc-duel");
    var msg = el("p", "", "panel__msg");
    msg.setAttribute("role", "status");
    function paintScore() {
      var n = count();
      score.textContent = n ? "You have judged " + n + " duel" + (n === 1 ? "" : "s") + " — the model thanks you." : "No duels judged yet. Your taste is training data.";
    }
    function comicCard(side, script, onVote) {
      var card = el("article", null, "oc-duel__card");
      card.append(el("h3", script.title, "oc-duel__title"));
      (script.panels || []).forEach(function (p, i) {
        var beat = el("div", null, "oc-duel__panel");
        beat.append(el("span", "Panel " + (i + 1), "oc-duel__beat"));
        beat.append(el("p", p.scene, "oc-duel__scene"));
        (p.lines || []).forEach(function (ln) { beat.append(el("p", ln, "oc-duel__line")); });
        card.append(beat);
      });
      card.append(el("p", script.caption || "", "oc-duel__caption"));
      var btn = el("button", side + " is funnier", "btn");
      btn.type = "button";
      btn.addEventListener("click", function () { onVote(side); });
      card.append(btn);
      return card;
    }
    function load() {
      msg.textContent = "Fetching two contenders…";
      arena.replaceChildren();
      host.get("/creative/duel").then(function (d) {
        msg.textContent = "";
        var done = false;
        function vote(winner) {
          if (done) return; done = true;
          host.post("/creative/duel/vote", {a_id: d.a.id, b_id: d.b.id, winner: winner})
            .then(function () { bump(); paintScore(); load(); })
            .catch(function (e) { done = false; msg.textContent = e.message || String(e); });
        }
        arena.append(
          comicCard("A", d.a, function () { vote(d.a.id); }),
          comicCard("B", d.b, function () { vote(d.b.id); })
        );
        var neither = el("button", "Neither — both missed", "btn ghost");
        neither.type = "button";
        neither.addEventListener("click", function () { vote("neither"); });
        arena.append(neither);
      }).catch(function (e) { msg.textContent = e.message || String(e); });
    }
    return {
      open: function () {
        if (!mount || mount.querySelector(".oc-duel")) { if (mount && !mount.querySelector(".oc-duel")) mount.append(score, arena, msg); paintScore(); return; }
        mount.replaceChildren();
        mount.append(score, arena, msg);
        paintScore();
        load();
      },
      reload: load
    };
  };
})();
