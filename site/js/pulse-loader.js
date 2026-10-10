/*! OddHobb Pulse: the loader engine.
 *
 * Plays a sprite-sheet animation on a heartbeat: each beat runs at a slightly
 * different speed, and the rest between beats breathes. It's regular overall,
 * but never mechanical. Modelled on real heart-rate variability:
 *
 *   interval_n = mean × (1 + rsa_n + drift_n + jitter_n), clamped
 *     rsa_n    slow sinusoid, like breathing (respiratory sinus arrhythmia)
 *     drift_n  AR(1) random walk: consecutive beats are correlated, not dice rolls
 *     jitter_n small independent noise
 *   speed follows the interval: a quicker beat plays quicker (like systole)
 *
 * Usage:
 *   <div data-pulse="emerge" style="--pulse-size:72px"></div>
 *   <script src="/js/pulse-loader.js"></script>   // auto-mounts
 *   const p = PulseLoader.mount(el, "emerge", {tempo: 1}); p.stop(); p.start(); p.destroy();
 *   PulseLoader.define("name", {sprite, frames, cols, px, beat:{...}})  // add a loader
 *
 * Respects prefers-reduced-motion (one still frame), pauses in background tabs,
 * draws on a DPR-aware canvas, and has no dependencies.
 */
(function (global) {
  "use strict";

  var PRESETS = {
    emerge: {
      sprite: "/assets/pulse/emerge.webp",
      frames: 66, cols: 11, px: 144,
      still: 30,                 // reduced-motion frame (full-front matte black mark)
      beat: {
        play: 2.9,               // seconds for one run of the sprite at tempo 1
        rest: 0.75,              // mean rest between runs
        speedRange: [0.84, 1.18],// bounds on play-speed factor
        restRange: [0.35, 1.35], // bounds on rest (seconds)
        rsa: 0.07, breathBeats: 4.3,
        drift: 0.05, driftMemory: 0.72,
        jitter: 0.025
      }
    }
  };

  function gauss() { // Box-Muller
    var u = 1 - Math.random(), v = Math.random();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }

  /** The rhythm generator, separate from drawing so other loaders can reuse it. */
  function Heart(cfg) {
    var n = 0, walk = 0, phase = Math.random() * Math.PI * 2;
    return {
      next: function (tempo) {
        n++;
        walk = cfg.driftMemory * walk + cfg.drift * gauss();
        var rsa = cfg.rsa * Math.sin(2 * Math.PI * n / cfg.breathBeats + phase);
        var dev = rsa + walk + cfg.jitter * gauss();           // + = slower, calmer beat
        var speed = clamp(1 - 0.9 * dev, cfg.speedRange[0], cfg.speedRange[1]) * (tempo || 1);
        var play = cfg.play / speed;
        var rest = clamp(cfg.rest * (1 + 1.6 * dev + 0.08 * gauss()), cfg.restRange[0], cfg.restRange[1]) / (tempo || 1);
        return { play: play, rest: rest, speed: speed };
      }
    };
  }

  var cache = {};
  function loadSprite(src) {
    if (!cache[src]) cache[src] = new Promise(function (res, rej) {
      var im = new Image(); im.decoding = "async";
      im.onload = function () { res(im); }; im.onerror = rej; im.src = src;
    });
    return cache[src];
  }

  function mount(el, name, opts) {
    opts = opts || {};
    var P = PRESETS[name]; if (!P) throw new Error("PulseLoader: unknown preset " + name);
    var cfg = Object.assign({}, P.beat, opts.beat || {});
    var tempo = opts.tempo || 1;
    var heart = Heart(cfg);
    var reduced = global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches;

    var cv = document.createElement("canvas");
    cv.setAttribute("role", "img"); cv.setAttribute("aria-label", opts.label || "Loading");
    cv.style.width = cv.style.height = "var(--pulse-size, 72px)";
    cv.style.display = "block";
    el.appendChild(cv);
    var ctx = cv.getContext("2d");

    var img = null, raf = 0, running = false, beat = null, t0 = 0, last = -1;
    function fit() {
      var css = cv.getBoundingClientRect().width || 72;
      var d = Math.min(global.devicePixelRatio || 1, 3);
      var s = Math.round(css * d);
      if (cv.width !== s) { cv.width = cv.height = s; last = -1; }
    }
    function draw(i) {
      if (!img || i === last) return; last = i;
      var c = i % P.cols, r = (i / P.cols) | 0;
      ctx.clearRect(0, 0, cv.width, cv.height);
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(img, c * P.px, r * P.px, P.px, P.px, 0, 0, cv.width, cv.height);
    }
    function tick(now) {
      if (!running) return;
      if (!beat) { beat = heart.next(tempo); t0 = now; }
      var t = (now - t0) / 1000;
      if (t < beat.play) {
        draw(Math.min(P.frames - 1, Math.floor(t / beat.play * P.frames)));
      } else if (t < beat.play + beat.rest) {
        draw(0);                                         // rest on the flat, near-invisible mark
      } else {
        beat = null;
      }
      raf = requestAnimationFrame(tick);
    }
    function start() {
      if (running) return; running = true; beat = null;
      if (reduced) { running = false; draw(P.still); return; }
      raf = requestAnimationFrame(tick);
    }
    function stop() { running = false; cancelAnimationFrame(raf); }
    function onVis() { document.hidden ? stop() : start(); }
    document.addEventListener("visibilitychange", onVis);
    global.addEventListener("resize", fit);

    loadSprite(opts.sprite || P.sprite).then(function (im) {
      img = im; fit(); last = -1;
      reduced ? draw(P.still) : start();
    });

    return {
      start: start, stop: stop,
      setTempo: function (x) { tempo = x; },
      destroy: function () {
        stop(); document.removeEventListener("visibilitychange", onVis);
        global.removeEventListener("resize", fit); cv.remove();
      },
      _heart: heart
    };
  }

  function define(name, preset) { PRESETS[name] = preset; }

  function auto() {
    document.querySelectorAll("[data-pulse]:not([data-pulse-mounted])").forEach(function (el) {
      el.setAttribute("data-pulse-mounted", "1");
      el._pulse = mount(el, el.getAttribute("data-pulse"), {
        tempo: parseFloat(el.getAttribute("data-pulse-tempo")) || 1,
        label: el.getAttribute("aria-label") || "Loading"
      });
    });
  }

  global.PulseLoader = { mount: mount, define: define, auto: auto, Heart: Heart, presets: PRESETS };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", auto); else auto();
})(window);
