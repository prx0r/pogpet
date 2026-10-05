/* Oddy avatar: inline-SVG state machine + analyser mouth.
 *
 * Zero HTTP requests: all 12 states ship as <symbol> defs in the page, and
 * paint() only swaps <use href>. States: idle/neutral breathing, listening,
 * thinking, speaking (small/wide from audio RMS, timer fallback for
 * speechSynthesis), overlays: confused/idea/happy/wink/sleepy/surprised/
 * delighted. Semantic tags: emotion, confidence (low -> confused), energy.
 * Rive later reuses this exact schema if swaps ever outgrow states.
 */
(function () {
  "use strict";

  var STATES = ["neutral", "listening", "thinking", "speaking-small",
    "speaking-wide", "confused", "idea", "happy", "wink", "sleepy",
    "surprised", "delighted"];

  var svgs = [];   // mounted <svg> elements, each containing one <use>
  var state = "neutral";
  var overlay = null;      // transient: idea/confused/etc, then falls back
  var overlayTimer = null;
  var mouthTimer = null;
  var analyser = null;
  var analyserData = null;
  var lastBase = "neutral";

  function paint() {
    var name = "#oddy-" + (overlay || state);
    for (var i = 0; i < svgs.length; i++) {
      var use = svgs[i].querySelector("use");
      if (use && use.getAttribute("href") !== name) use.setAttribute("href", name);
    }
  }

  function rms() {
    if (!analyser || !analyserData) return -1;
    analyser.getByteTimeDomainData(analyserData);
    var sum = 0;
    for (var i = 0; i < analyserData.length; i++) {
      var v = (analyserData[i] - 128) / 128;
      sum += v * v;
    }
    return Math.sqrt(sum / analyserData.length);
  }

  var liveSvg = null, liveMouth = null, liveHead = null;
  var smOpen = 0, smWide = 0.5;

  function bands() {
    // multiband faked visemes: low->round(O/U), mid->open(A/E), high->narrow
    if (!analyser || !analyserData) return null;
    analyser.getByteFrequencyData(analyserData);
    function avg(a, b) {
      var s = 0, n = 0;
      for (var i = a; i < b && i < analyserData.length; i++) { s += analyserData[i] / 255; n++; }
      return n ? s / n : 0;
    }
    var low = avg(1, 8), mid = avg(8, 40), high = avg(40, 120);
    return {
      open: low * 0.25 + mid * 0.75,
      wide: Math.max(0, mid - low),
      round: Math.max(0, low - high),
      energy: (low + mid + high) / 3
    };
  }

  function morphMouth(b) {
    // continuous morph: rx from width, ry from openness; head bobs 1-2px
    if (!liveMouth) return;
    smOpen = smOpen * 0.72 + b.open * 0.28;
    smWide = smWide * 0.72 + (0.35 + b.wide) * 0.28;
    var rx = 8 + Math.min(1, smWide) * 12;
    var ry = 3 + Math.min(1, smOpen) * 19;
    liveMouth.setAttribute("rx", rx.toFixed(1));
    liveMouth.setAttribute("ry", ry.toFixed(1));
    if (liveHead) liveHead.setAttribute("transform",
      "translate(0 " + (-Math.min(1, b.energy) * 2).toFixed(2) + ")");
  }

  function mouthTick() {
    var level = rms();
    if (liveSvg && liveMouth && level >= 0) {
      var b = bands();
      if (b) morphMouth(b);
      return; // morph path: no file swaps while live audio drives
    }
    if (level < 0) {
      // speechSynthesis has no audio tap: alternate mouths on a timer
      lastBase = lastBase === "speaking-small" ? "speaking-wide" : "speaking-small";
      state = lastBase;
    } else {
      state = level > 0.08 ? "speaking-wide" : "speaking-small";
    }
    paint();
  }

  window.Oddy = {
    states: STATES,

    mount: function (svg) {
      if (!svg) return;
      svgs.push(svg);
      paint();
    },

    set: function (s) {
      if (STATES.indexOf(s) < 0) return;
      overlay = null;
      state = s;
      lastBase = (s === "speaking-small" || s === "speaking-wide") ? s : lastBase;
      paint();
    },

    get: function () { return overlay || state; },

    // transient overlay (idea/confused/delighted…), auto falls back
    flash: function (s, ms) {
      if (STATES.indexOf(s) < 0) return;
      overlay = s;
      paint();
      if (overlayTimer) clearTimeout(overlayTimer);
      overlayTimer = setTimeout(function () {
        overlay = null;
        paint();
      }, ms || 2200);
    },

    // semantic tags from model/orchestrator
    semantic: function (tag) {
      tag = tag || {};
      if (tag.emotion && STATES.indexOf(tag.emotion) >= 0) {
        if (tag.emotion === "neutral" || tag.emotion === "happy") this.set(tag.emotion);
        else this.flash(tag.emotion);
        return;
      }
      if (typeof tag.confidence === "number" && tag.confidence < 0.4) {
        this.flash("confused");
        return;
      }
      if (tag.toolSuccess) {
        this.flash("idea");
        return;
      }
    },

    // bind a live AnalyserNode (LiveKit track / mic stream); null detaches
    bindAnalyser: function (node) {
      analyser = node || null;
      analyserData = node ? new Uint8Array(node.fftSize) : null;
    },

    speakingStart: function () {
      this.set("speaking-small");
      if (mouthTimer) clearInterval(mouthTimer);
      mouthTimer = setInterval(mouthTick, 160);
    },

    speakingStop: function () {
      if (mouthTimer) { clearInterval(mouthTimer); mouthTimer = null; }
      this.showLive(false);
      if (state === "speaking-small" || state === "speaking-wide") {
        this.set("neutral");
      }
    },

    // live morph view: continuous mouth while real audio drives; the
    // swap-files stay for emotions and for speechSynthesis (no tap)
    mountLive: function (svgId, mouthId, headId) {
      liveSvg = document.getElementById(svgId) || null;
      liveMouth = document.getElementById(mouthId) || null;
      liveHead = document.getElementById(headId) || null;
    },

    showLive: function (on) {
      var live = document.getElementById("oddy-live-morph");
      var swap = document.getElementById("oddy-live");
      if (live) live.style.display = on ? "" : "none";
      if (swap) swap.style.display = on ? "none" : "";
    }
  };
})();
