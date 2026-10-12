// Pogtown Comedy Club — plays a Rive set live in the browser.
// ClubBack -> Character -> ClubFront on one canvas, one camera, driven by the director's baked
// keyframes (assets/club/<id>/set.json, written by scripts/club_bundle.py). Real-time port of
// rivelab player/compose.html. Falls back to the set's rendered MP4 when WASM/Rive cannot start.
// Usage: import('/js/club-player.js').then(m => m.mountClub(document.getElementById('club')))
const RIVE_DIR = '/vendor/rive-canvas-advanced-2.44.2/';
const BASE = '/assets/club/';
const FW = 1080, FH = 1920;               // director frame space (9:16)

function sample(tr, t) {                  // linear interpolation in a [[t, v], ...] track
  if (!tr || !tr.length) return null;
  if (t <= tr[0][0]) return tr[0][1];
  let lo = 0, hi = tr.length - 1;
  if (t >= tr[hi][0]) return tr[hi][1];
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (tr[m][0] <= t) lo = m; else hi = m; }
  const a = tr[lo], b = tr[hi], u = (t - a[0]) / Math.max(1e-6, b[0] - a[0]);
  return a[1] + (b[1] - a[1]) * u;
}
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fetchBytes = async u => { const r = await fetch(u); if (!r.ok) throw new Error(u + ' ' + r.status); return new Uint8Array(await r.arrayBuffer()); };

export async function mountClub(root) {
  if (!root || root.__club) return root && root.__club;
  const $ = s => root.querySelector(s);
  const stage = $('.club__stage'), cv = $('.club__canvas'), vid = $('.club__video');
  const capEl = $('.club__cap'), tagEl = $('.club__tag'), pick = $('.club__pick');
  const muteBtn = $('.club__mute'), tapBtn = $('.club__tap'), modeEl = $('.club__mode'), note = $('.club__note');
  const S = { mode: 'loading', set: null, plan: null, t: 0, frames: 0, playing: true, muted: true, visible: true,
              wall0: 0, lastT: 0, capIdx: -2, sets: [], error: null };
  root.__club = S; window.__club = S;

  let manifest;
  try { manifest = await (await fetch(BASE + 'manifest.json')).json(); }
  catch (e) { if (note) note.textContent = 'Comedy club unavailable.'; S.mode = 'error'; return S; }
  S.sets = manifest.sets || [];
  pick.innerHTML = S.sets.map((s, i) =>
    '<button type="button" class="chip' + (i ? '' : ' on') + '" data-set="' + esc(s.id) + '">' + esc(s.title) + '</button>').join('');

  // ── audio ───────────────────────────────────────────────
  const audio = new Audio(); audio.preload = 'auto';
  function clockNow() {
    if (!S.muted && !audio.paused && audio.readyState >= 2) return audio.currentTime;
    return (performance.now() - S.wall0) / 1000;
  }
  function setClock(t) { S.wall0 = performance.now() - t * 1000; if (!S.muted) { try { audio.currentTime = t; } catch (e) {} } }

  // ── mode: live Rive or MP4 fallback ─────────────────────
  let rive = null, renderer = null, g2 = null, back = null, front = null, chr = null, clubBytes = null;
  const forceMp4 = /[?&]club=mp4\b/.test(location.search) || typeof WebAssembly !== 'object';

  async function loadAB(bytes, abName, smName) {
    const f = await rive.load(bytes);
    const ab = f.artboardByName(abName);
    const smDef = smName ? (ab.stateMachineByName(smName) || ab.stateMachineByIndex(0)) : ab.stateMachineByIndex(0);
    const sm = new rive.StateMachineInstance(smDef, ab);
    let vmi = null;
    const vm = f.defaultArtboardViewModel ? f.defaultArtboardViewModel(ab) : null;
    if (vm) { vmi = vm.defaultInstance(); sm.bindViewModelInstance(vmi); }
    const IN = {};
    for (let i = 0; i < sm.inputCount(); i++) { const x = sm.input(i); IN[x.name] = x; }
    return { f, ab, sm, smDef, vmi, IN, nums: {} };
  }
  function num(o, k) { if (!o || !o.vmi) return null; if (!(k in o.nums)) o.nums[k] = o.vmi.number(k); return o.nums[k]; }
  function setInput(o, k, v) {
    const x = o.IN[k];
    if (x) {
      if (x.type === rive.SMIInput.trigger) { if (v !== false) x.asTrigger().fire(); }
      else if (x.type === rive.SMIInput.bool) x.asBool().value = !!v;
      else x.asNumber().value = +v;
      return;
    }
    const n = num(o, k); if (n) n.value = +v;
  }
  function freeAB(o) { if (!o) return; for (const k of ['sm', 'ab']) { try { o[k].delete(); } catch (e) {} } }

  function applyInit() {
    const P = S.plan;
    for (const o of [back, front]) if (o && o.vmi && P.world) { const s = o.vmi.string('worldName'); if (s) s.value = P.world; }
    for (const [k, v] of Object.entries(P.init || {})) setInput(chr, k, v);
  }
  function restartActing() {           // loop / set switch: fresh state machine so triggers replay cleanly
    if (!chr) return;
    try { chr.sm.delete(); } catch (e) {}
    chr.sm = new rive.StateMachineInstance(chr.smDef, chr.ab);
    if (chr.vmi) chr.sm.bindViewModelInstance(chr.vmi);
    chr.IN = {}; for (let i = 0; i < chr.sm.inputCount(); i++) { const x = chr.sm.input(i); chr.IN[x.name] = x; }
    applyInit();
  }

  async function initRive() {
    const mod = await import(RIVE_DIR + 'canvas_advanced.mjs');
    rive = await mod.default({ locateFile: f => RIVE_DIR + (f.endsWith('.wasm') ? 'rive.wasm' : f) });
    g2 = cv.getContext('2d');
    renderer = rive.makeRenderer(cv);
    clubBytes = await fetchBytes(BASE + (manifest.club_riv || 'club.riv'));
    back = await loadAB(clubBytes, 'ClubBack');
    front = await loadAB(clubBytes, 'ClubFront');
  }

  function useMp4(why) {
    S.mode = 'mp4'; if (why) S.error = String(why && why.message || why);
    cv.hidden = true; capEl.hidden = true; tagEl.hidden = true; vid.hidden = false;
    modeEl.textContent = 'video';
    if (S.set) showMp4(S.set);
  }
  function showMp4(s) {
    if (!s.mp4) { note.textContent = 'No video for this set yet.'; return; }
    vid.poster = s.poster ? BASE + s.poster : '';
    vid.src = BASE + s.mp4; vid.muted = S.muted; vid.loop = true;
    if (S.playing && S.visible) vid.play().catch(() => {});
  }

  async function selectSet(id) {
    const s = S.sets.find(x => x.id === id) || S.sets[0]; if (!s) return;
    S.set = s; S.capIdx = -2; capEl.innerHTML = '';
    pick.querySelectorAll('[data-set]').forEach(b => b.classList.toggle('on', b.getAttribute('data-set') === s.id));
    stage.style.setProperty('--club-accent', s.color || '#c4891a');
    audio.pause(); audio.src = s.audio ? BASE + s.audio : '';
    if (S.mode === 'mp4') { showMp4(s); return; }
    note.textContent = 'Warming up ' + s.title + '…';
    try {
      const [plan, bytes] = await Promise.all([fetch(BASE + s.set).then(r => r.json()), fetchBytes(BASE + s.riv)]);
      if (S.set !== s) return;                       // user switched again while loading
      const next = await loadAB(bytes, plan.artboard || 'Character', plan.stateMachine || 'Acting');
      freeAB(chr); chr = next; S.plan = plan;
      applyInit(); S.lastT = 0; setClock(0);
      if (!S.muted) audio.play().catch(() => {});
      note.textContent = '';
    } catch (e) { console.warn('club: rive set failed, using MP4', e); useMp4(e); }
  }

  // ── sizing ──────────────────────────────────────────────
  function fit() {
    const r = stage.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(180, Math.min(FW, Math.round(r.width * dpr)));
    const h = Math.round(w * FH / FW);
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
  }

  // ── frame ───────────────────────────────────────────────
  function drawChar(cam) {
    const P = S.plan, pl = P.char_place || {}, CW = cv.width, CH = cv.height;
    const s = pl.scale || 1, bx = FW / 2, by = FH, dx = pl.dx || 0, dy = pl.dy || 0;
    const z = cam.z * s, fx = bx - (bx - cam.fx) / s - dx / s, fy = by - (by - cam.fy) / s - dy / s;
    const hw = FW / 2 / z, hh = FH / 2 / z;
    renderer.save();
    renderer.align(rive.Fit.fill, rive.Alignment.center, { minX: 0, minY: 0, maxX: CW, maxY: CH },
                   { minX: fx - hw, minY: fy - hh, maxX: fx + hw, maxY: fy + hh });
    chr.ab.draw(renderer); renderer.restore();
  }
  function drawFull(o) {
    renderer.save();
    renderer.align(rive.Fit.fill, rive.Alignment.center, { minX: 0, minY: 0, maxX: cv.width, maxY: cv.height }, o.ab.bounds);
    o.ab.draw(renderer); renderer.restore();
  }
  function captions(t) {
    const caps = S.plan.captions || [];
    const i = caps.findIndex(c => t >= c.t0 && t <= c.t1 + 0.15);
    if (i !== S.capIdx) {
      S.capIdx = i;
      capEl.innerHTML = i < 0 ? '' : caps[i].words.map(w => '<span>' + esc(w.w) + '</span>').join(' ');
    }
    if (i >= 0) caps[i].words.forEach((w, k) => { const sp = capEl.children[k]; if (sp) sp.classList.toggle('on', t >= w.t0 && t <= w.t1 + 0.05); });
  }
  function tagFx(t) {
    const g = S.plan.tag;
    if (!g || t < g.t0 || t > g.t1) { tagEl.style.opacity = 0; return; }
    if (!tagEl.dataset.id || tagEl.dataset.id !== S.set.id) {
      tagEl.dataset.id = S.set.id;
      tagEl.innerHTML = '<b>' + esc(g.name) + '</b><span>' + esc(g.sub) + '</span>';
      tagEl.style.borderLeftColor = g.color || '#c4891a';
    }
    tagEl.style.opacity = Math.max(0, Math.min(1, (t - g.t0) / 0.25, (g.t1 - t) / 0.25));
  }

  function frame() {
    requestAnimationFrame(frame);
    if (S.mode !== 'live' || !chr || !S.plan || !S.playing || !S.visible || document.hidden) return;
    const P = S.plan;
    let t = clockNow();
    if (t >= P.duration) {                           // loop the set
      t = 0; setClock(0); restartActing(); S.lastT = 0; S.capIdx = -2;
      if (!S.muted) { audio.currentTime = 0; audio.play().catch(() => {}); }
    }
    const t0 = S.lastT, dt = Math.min(0.1, Math.max(0, t - t0)); S.lastT = t; S.t = t;
    for (const e of P.events || []) if (e.t > t0 && e.t <= t) setInput(chr, e.input, e.value === undefined ? true : e.value);
    for (const k in P.vm) { const n = num(chr, k); if (n) n.value = sample(P.vm[k], t); }
    const cvv = {}; for (const k in P.club || {}) cvv[k] = sample(P.club[k], t);
    for (const o of [back, front]) for (const k in cvv) { const n = num(o, k); if (n) n.value = cvv[k]; }
    const cam = { z: 1 + (cvv.camZoom || 0), fx: FW / 2 + (cvv.camX || 0), fy: FH / 2 + (cvv.camY || 0) };
    for (const o of [back, chr, front]) { o.sm.advanceAndApply(dt); o.ab.advance(dt); }
    renderer.clear();
    drawFull(back); drawChar(cam); drawFull(front);
    renderer.flush(); rive.resolveAnimationFrame();
    const fade = Math.max(0, 1 - t / (P.fadeIn || 0.001), (t - (P.duration - (P.fadeOut || 0))) / (P.fadeOut || 1e9));
    if (fade > 0) { g2.save(); g2.setTransform(1, 0, 0, 1, 0, 0); g2.fillStyle = 'rgba(0,0,0,' + Math.min(1, fade) + ')'; g2.fillRect(0, 0, cv.width, cv.height); g2.restore(); }
    captions(t); tagFx(t);
    S.frames++;
  }

  // ── controls ────────────────────────────────────────────
  pick.addEventListener('click', e => { const b = e.target.closest('[data-set]'); if (b) selectSet(b.getAttribute('data-set')); });
  muteBtn.addEventListener('click', e => {
    e.stopPropagation();
    S.muted = !S.muted; muteBtn.textContent = S.muted ? '🔇' : '🔊';
    muteBtn.setAttribute('aria-label', S.muted ? 'Unmute' : 'Mute');
    if (S.mode === 'mp4') { vid.muted = S.muted; if (!S.muted) vid.play().catch(() => {}); return; }
    const t = S.t;
    if (S.muted) { audio.pause(); setClock(t); }
    else { try { audio.currentTime = t; } catch (_) {} audio.play().catch(() => {}); }
  });
  tapBtn.addEventListener('click', () => {
    S.playing = !S.playing; stage.classList.toggle('paused', !S.playing);
    if (S.mode === 'mp4') { S.playing ? vid.play().catch(() => {}) : vid.pause(); return; }
    if (S.playing) { setClock(S.t); if (!S.muted) audio.play().catch(() => {}); } else audio.pause();
  });
  if ('IntersectionObserver' in window) new IntersectionObserver(es => es.forEach(en => {
    const was = S.visible; S.visible = en.isIntersecting;
    if (was === S.visible) return;
    if (!S.visible) { audio.pause(); if (S.mode === 'mp4') vid.pause(); }
    else if (S.playing) { if (S.mode === 'mp4') vid.play().catch(() => {}); else { setClock(S.t); if (!S.muted) audio.play().catch(() => {}); } }
  }), { threshold: 0.2 }).observe(stage);
  // keep the wall clock honest across tab switches (rAF stops while hidden)
  document.addEventListener('visibilitychange', () => { if (!document.hidden && S.mode === 'live') setClock(S.t); });
  if ('ResizeObserver' in window) new ResizeObserver(fit).observe(stage); else window.addEventListener('resize', fit);
  fit();

  if (forceMp4) { useMp4('forced'); await selectSet(S.sets[0] && S.sets[0].id); return S; }
  try {
    modeEl.textContent = 'live';
    await initRive();
    S.mode = 'live';
  } catch (e) { console.warn('club: rive unavailable, using MP4', e); useMp4(e); }
  await selectSet(S.sets[0] && S.sets[0].id);
  requestAnimationFrame(frame);
  return S;
}
