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

  function mouthTick() {
    var level = rms();
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
      if (state === "speaking-small" || state === "speaking-wide") {
        this.set("neutral");
      }
    }
  };
})();
