/* OddHobb /cards: upload a photo, get cards made automatically.
 *
 * The one customer flow for paper cards, on the canonical cardgen engine:
 *   1 who + occasion (+ relationship, one or two interests for the joke)
 *   2 upload 1-3 photos -> faces detected on upload -> tap their face if several
 *   3 POST /cardgen/recommend -> the templates these photos can make
 *   4 POST /cardgen/make for the top 4, poll /cardgen/jobs/<id> (step by step)
 *   5 pick one -> the card opens front -> inside -> back (StPageFlip, hard covers; the three
 *     static faces stay as the fallback). The inside message previews live as you type and is
 *     only saved as a new revision and re-rendered on Apply (the painted art never changes)
 *   6 Buy -> export render -> POST /cards/<id>/checkout -> Shopify checkout_url
 *
 * Replaces the legacy PIL shelf (arch/dots/gold/news/wall backdrops and the
 * photo-in-a-frame gallery). No collage fallback: when no template can be cast
 * from the photos, the customer is told which photo would unlock one.
 *
 * host: {get(path), post(path, body), asset(path), upload(file)}, the same host
 * object index.html already builds for the card studio (paths are /backend/api relative).
 */
(function () {
  'use strict';
  var MAX_CARDS = 4, POLL_MS = 3000, JOB_TIMEOUT_MS = 6 * 60 * 1000;
  // only occasions a cardgen template declares (cardgen/templates/*.json "occasions")
  var OCCASIONS = [['birthday', 'Birthday'], ['christmas', 'Christmas'], ['fathers_day', "Father's Day"],
    ['mothers_day', "Mother's Day"], ['retirement', 'Retirement'], ['anniversary', 'Anniversary'], ['valentines', "Valentine's"]];
  function occasionLabel(v) { var o = OCCASIONS.find(function (x) { return x[0] === v; }); return o ? o[1] : v; }
  var GRID_CHOICES = [['4', 'Four photos'], ['1', 'One big photo'], ['10', 'Ten photos']];
  var STYLE_CHOICES = [['', 'Pick for me'], ['classic', 'Classic gold'], ['bold', 'Bold modern'], ['playful', 'Playful'],
    ['botanical', 'Botanical'], ['sporty', 'Sporty'], ['kids', 'Kids']];
  var STEP_LABEL = { queued: 'Queued', index: 'Reading the photos', write: 'Writing the joke', generate: 'Painting the front',
    qa0: 'Checking likeness', qa1: 'Fixing details', qa2: 'Final check', spot: 'Painting the inside', upscale: 'Sharpening for print',
    freeze: 'Setting the card', done: 'Ready' };

  function el(tag, text, cls) { var n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; }
  function btn(text, fn, cls) { var b = el('button', text, cls || 'ca-btn'); b.type = 'button'; b.addEventListener('click', fn); return b; }
  function field(label, input) { var l = el('label', null, 'ca-field'); l.append(el('span', label), input); return l; }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function idem(prefix) { return prefix + '-' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10); }

  window.OddHobbAutoCards = function (host) {
    var panel = document.querySelector('#panel-cards .panel__inner');
    var st = { subject: null, photos: [], occasion: 'birthday', relationship: '', interests: [], name: '', jobs: [], pick: null, busy: false, price: '' };
    // the one card price, read from the backend's card product (cards.card_price), never hardcoded
    var pricePromise = null;
    function cardPrice() {
      if (!pricePromise) pricePromise = host.get('/cards/templates').then(function (r) {
        st.price = (r.product && r.product.price) || ''; return st.price;
      }).catch(function () { pricePromise = null; return ''; });
      return pricePromise;
    }
    var root = el('div', null, 'ca'), status = el('p', '', 'ca-status');
    status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');

    function say(t, bad) { status.textContent = t || ''; status.classList.toggle('ca-status--bad', !!bad); }
    function fail(e) { st.busy = false; say((e && e.message) || String(e), true); }
    function mount() { if (panel && !panel.contains(root)) { panel.replaceChildren(root); } }

    // ── step 1+2: who, occasion, photos ────────────────────────────────
    // Your photos live on the site already — cards inherit them. Existing
    // people come first as one-tap chips (zero new uploads needed); the
    // form below is only for someone new.
    function startView() {
      st.jobs = []; st.pick = null;
      var head = el('div', null, 'store-head');
      var priceLine = el('p', '', 'ca-price'); priceLine.hidden = true;
      cardPrice().then(function (p) { if (p) { priceLine.textContent = 'From ' + p + ', printed and posted.'; priceLine.hidden = false; } });
      head.append(el('h2', 'Birthday cards made from your photos'), priceLine, el('p', 'Pick someone — we use their saved photos, pick the best ones, and set them under a Happy Birthday header, ready in seconds.'));
      var people = el('div', null, 'ca-people');
      var examples = el('div', null, 'ca-examples');
      var exRow = el('div', null, 'ca-examples__row');
      [['/img/cards/example-golf-front.png', 'Golf birthday, front'],
       ['/img/cards/example-golf-inside.png', 'Golf birthday, inside'],
       ['/img/cards/example-golf-back.png', 'Golf birthday, back']].forEach(function (x) {
        var f = el('figure', null, 'ca-example');
        var im = el('img'); im.alt = x[1]; im.loading = 'lazy'; im.src = x[0];
        var cap = el('figcaption', x[1]);
        f.append(im, cap); exRow.append(f);
      });
      examples.append(el('h3', 'Finished cards — yours will star your people'),
        el('p', 'A real birthday card we made: painted front, message inside, clean back. Pick someone below and we make theirs.'),
        exRow);
      var form = el('div', null, 'ca-form');
      var who = el('select'); who.append(new Option('Someone new', ''));
      var name = el('input'); name.maxLength = 60; name.placeholder = 'Dad, Mum, Biscuit the dog…';
      var rel = el('input'); rel.maxLength = 40; rel.placeholder = 'dad, best friend, our dog';
      var interests = el('input'); interests.maxLength = 120; interests.placeholder = 'golf, Tesla, terrible puns';
      var occ = el('select'); occ.append(new Option('Birthday', 'birthday'));
      var age = el('input'); age.type = 'number'; age.min = 1; age.max = 120; age.placeholder = 'e.g. 70 (optional)';
      var gridSel = el('select'); GRID_CHOICES.forEach(function (g) { gridSel.append(new Option(g[1], g[0])); });
      var styleSel = el('select'); STYLE_CHOICES.forEach(function (g) { styleSel.append(new Option(g[1], g[0])); });
      var kind = el('select'); kind.append(new Option('Person', 'person'), new Option('Pet', 'pet'));
      var file = el('input'); file.type = 'file'; file.accept = 'image/jpeg,image/png,image/webp'; file.multiple = true;
      var thumbs = el('div', null, 'ca-thumbs');
      var savedNote = el('p', '', 'ca-status');
      var newOnly = el('div', null, 'ca-new'); newOnly.append(field('Their name', name), field('Person or pet', kind));
      var identity = el('div', null, 'ca-identity');
      var whoField = field('Who is it for?', who);
      var relField = field('Who are they to you?', rel);
      var intField = field('What are they into? (for the joke)', interests);
      var photoField = field('Photos of them (up to 10, faces clear)', file);
      identity.append(whoField, newOnly, relField, intField, photoField);
      var forLine = el('p', '', 'ca-forline');
      var changeBtn = btn('Change person', function () {
        who.value = ''; newOnly.hidden = false; identity.hidden = false;
        forLine.hidden = true; savedNote.textContent = ''; photoLabel();
      }, 'ca-btn ca-btn--ghost');
      forLine.hidden = true;
      function photoLabel() {
        // a new person needs a photo; someone already saved has theirs, so more are optional
        photoField.firstChild.textContent = who.value ? 'More photos of them (optional, we already have theirs)' : 'Photos of them (up to 10, faces clear)';
      }
      function pickPerson(id) {
        who.value = id;
        newOnly.hidden = true;
        photoLabel();
        var s = (st.library && st.library.subjects || []).find(function (x) { return x.id === id; });
        if (s) {
          rel.value = s.relationship || ''; interests.value = (s.interests || []).join(', ');
          identity.hidden = true;
          forLine.hidden = false;
          forLine.textContent = 'For ' + s.name +
            (s.photo_count ? ' · ' + s.photo_count + ' saved photos' : '') +
            ' — photos inherited, set the card below and hit the button.';
        }
      }
      who.addEventListener('change', function () {
        newOnly.hidden = !!who.value; photoLabel();
        if (!who.value) {
          identity.hidden = false; forLine.hidden = true; savedNote.textContent = '';
          return;
        }
        pickPerson(who.value);
      });
      file.addEventListener('change', function () {
        thumbs.replaceChildren();
        Array.prototype.slice.call(file.files, 0, 10).forEach(function (f) { var i = el('img'); i.alt = ''; i.src = URL.createObjectURL(f); thumbs.append(i); });
      });
      var go = btn('Make my cards', function () {
        if (st.busy) return;
        var files = Array.prototype.slice.call(file.files || [], 0, 10);
        if (!who.value && !name.value.trim()) return say('Tell us their name first.', true);
        if (!who.value && !files.length) return say('Add at least one clear photo of them.', true);
        st.occasion = occ.value; st.relationship = rel.value.trim();
        st.interests = interests.value.split(',').map(function (s) { return s.trim(); }).filter(Boolean).slice(0, 6);
        st.age = parseInt(age.value, 10) || 0; st.grid = parseInt(gridSel.value, 10) || 4; st.style = styleSel.value;
        st.busy = true; go.disabled = true;
        prepare(who.value, name.value.trim(), kind.value, files).then(makeGrid).catch(fail).then(function () { go.disabled = false; });
      }, 'ca-btn ca-btn--go');
      go.textContent = 'Make my card';
      form.append(identity, forLine, changeBtn,
        field('Age they are turning', age), field('Photos on the front', gridSel), field('Lettering', styleSel),
        savedNote, thumbs, go);
      root.replaceChildren(head, examples, people, form, status); mount(); say('');
      host.get('/studio/library').then(function (lib) {
        st.library = lib;
        var subs = (lib.subjects || []).filter(function (s) { return s.name; });
        subs.forEach(function (s) { who.append(new Option(s.name, s.id)); });
        // one-tap chips from saved photos — no uploads, no form
        people.replaceChildren();
        if (subs.length) {
          people.append(el('h3', 'Your people — tap one'));
          var row = el('div', null, 'ca-people__row');
          subs.forEach(function (s) {
            var mine = (lib.photos || []).filter(function (p) {
              return (p.subjects || []).some(function (l) { return l.subject_id === s.id && l.confirmed; });
            });
            s.photo_count = mine.length;
            var chip = el('button', null, 'ca-person'); chip.type = 'button';
            if (mine.length && mine[0].thumbnail_url) {
              var im = el('img'); im.alt = s.name; im.loading = 'lazy';
              im.src = host.asset(mine[0].thumbnail_url);
              chip.append(im);
            } else {
              chip.append(el('span', (s.name || '?').charAt(0).toUpperCase(), 'ca-person__initial'));
            }
            chip.append(el('span', s.name + (mine.length ? ' · ' + mine.length : ''), 'ca-person__name'));
            chip.setAttribute('aria-label', 'Make a card for ' + s.name + ' from saved photos');
            chip.addEventListener('click', function () { pickPerson(s.id); });
            row.append(chip);
          });
          people.append(row);
        }
      }).catch(function () { /* first visit: no library yet */ });
    }

    // create/reuse the subject, upload, link faces, save profile
    function prepare(sid, name, kind, files) {
      var p = Promise.resolve(sid);
      if (!sid) {
        say('Saving ' + name + '…');
        p = host.post('/studio/subjects', { name: name, kind: kind }).then(function (r) { return r.subject.id; });
      }
      return p.then(function (id) {
        st.subject = id; st.name = name || subjectName(id);
        var known = (st.library && st.library.subjects || []).find(function (x) { return x.id === id; });
        st.kind = sid ? ((known && known.kind) || 'person') : kind;
        var chain = Promise.resolve(), uploaded = [];
        files.forEach(function (f, i) {
          chain = chain.then(function () {
            say('Uploading photo ' + (i + 1) + ' of ' + files.length + '…');
            return host.upload(f).then(function (r) { uploaded.push(r.photo.id); });
          });
        });
        return chain.then(function () { return uploaded; });
      }).then(function (pids) {
        if (!pids.length) return;
        return host.get('/studio/library').then(function (lib) {
          st.library = lib;
          var chain = Promise.resolve();
          pids.forEach(function (pid) {
            var photo = (lib.photos || []).find(function (x) { return x.id === pid; });
            if (!photo) return;
            chain = chain.then(function () { return linkFace(photo); });
          });
          return chain;
        });
      }).then(function () {
        var prof = {};
        if (st.relationship) prof.relationship = st.relationship;
        if (st.interests.length) prof.interests = st.interests;
        if (Object.keys(prof).length) return host.post('/studio/subjects/' + st.subject + '/profile', prof).catch(function () {});
      });
    }

    function subjectName(id) {
      var s = (st.library && st.library.subjects || []).find(function (x) { return x.id === id; });
      return (s && s.name) || 'them';
    }

    // One face: link it. Several: ask which one is them. None: link the photo (pets, profiles).
    function linkFace(photo) {
      var faces = photo.faces || [];
      var keep = (photo.subjects || []).filter(function (l) { return l.subject_id !== st.subject; })
        .map(function (l) { return { subject_id: l.subject_id, face_id: l.face_id || '' }; });
      function save(fid) { return host.post('/studio/photos/' + photo.id, { subjects: keep.concat([{ subject_id: st.subject, face_id: fid || '' }]) }); }
      if (st.kind === 'pet') return save('');  // a pet is tagged by photo, never by a human face in it
      if (faces.length <= 1) return save(faces[0] && faces[0].id);
      return new Promise(function (resolve, reject) {
        var box = el('div', null, 'ca-faces');
        box.append(el('h3', 'Which one is ' + st.name + '?'));
        var row = el('div', null, 'ca-faces__row');
        faces.forEach(function (f) {
          var b = el('button', null, 'ca-face'); b.type = 'button';
          var img = el('img'); img.alt = 'Face'; img.src = host.asset(photo.thumbnail_url + '&face_id=' + encodeURIComponent(f.id));
          b.append(img);
          b.addEventListener('click', function () { box.remove(); save(f.id).then(resolve, reject); });
          row.append(b);
        });
        box.append(row, btn('Not in this photo', function () { box.remove(); resolve(); }, 'ca-btn ca-btn--ghost'));
        root.insertBefore(box, status); say('');
      });
    }

    // ── step 3+4: recommend, make, poll ────────────────────────────────
    function profile() {
      var p = { name: st.name };
      if (st.kind === 'pet') p.pet_name = st.name;
      if (st.relationship) { p.relationship = st.relationship; p.recipient = st.name; }
      if (st.interests.length) p.interests = st.interests;
      p.occasion = st.occasion;
      return p;
    }

    // ── the photo-grid card: instant, no painting, no daily cap ─────────
    function gridJob(r) {
      return { design_id: r.design_id, revision: r.revision, template: 'photo_grid', grid: r.grid, style: r.style,
        copy: { inside: ((((r.design || {}).spec || {}).inside || {}).right || {}).message || '', sender: '' },
        views: viewsFor(r.design_id, r.revision), product: r.product, selection: r.selection };
    }
    function makeGrid() {
      say('Choosing the best photos of ' + st.name + '…');
      var body = { subject_id: st.subject, photos: st.grid || 4, style: st.style || '', age: st.age || 0, tone: '' };
      return host.post('/cards/photo-grid', body).then(function (r) {
        st.busy = false; st.product = r.product;
        var j = gridJob(r);
        return renderAndWait(j.design_id, j.revision, 'preview').then(function () {
          detailView(j);
          if (r.selection && r.selection.summary) say(r.selection.summary);
        });
      }, function (e) {
        st.busy = false;
        var box = el('div', null, 'ca-blocked');
        box.append(el('h3', 'We need clearer photos of ' + st.name), el('p', (e && e.message) || 'Add a sharp photo where their face is big.'));
        box.append(btn('Add another photo', startView));
        root.replaceChildren(box, status); say('');
      });
    }

    // change a photo-grid card: swap a photo, the count or the lettering -> new revision
    function changeGrid(j, change) {
      say('Updating your card…');
      return host.get('/cards/designs/' + j.design_id).then(function (cur) {
        return host.post('/cards/photo-grid', Object.assign({ design_id: j.design_id, expected_revision: cur.design.revision }, change));
      }).then(function (r) {
        j.revision = r.revision; j.grid = r.grid; j.style = r.style; j.selection = r.selection || j.selection;
        return renderAndWait(j.design_id, j.revision, 'preview').then(function () { return r; });
      });
    }

    function recommend() {
      say('Finding the cards these photos can make…');
      return host.post('/cardgen/recommend', { subject_id: st.subject, occasion: st.occasion, profile: profile() }).then(function (r) {
        var ready = (r.ready || []).slice(0, MAX_CARDS);
        if (!ready.length) { st.busy = false; return blockedView(r); }
        return host.get('/cardgen/status').catch(function () { return { can_generate: true }; }).then(function (h) {
          if (h && h.can_generate === false) {
            st.busy = false;
            say('Your photos are saved, but card painting is switched off on our side right now. Please try again shortly.', true);
            return;
          }
          return makeAll(ready);
        });
      });
    }

    function makeAll(ready) {
      {
        st.jobs = ready.map(function (t) { return { template_id: t.template_id, status: 'queued', step: 'queued' }; });
        makingView();
        return Promise.all(st.jobs.map(function (j) {
          return host.post('/cardgen/make', { subject_id: st.subject, template_id: j.template_id, occasion: st.occasion, profile: profile() })
            .then(function (m) { j.id = m.job_id; return poll(j); })
            .catch(function (e) { j.status = 'failed'; j.error = (e && e.message) || 'Could not start'; drawJobs(); });
        })).then(function () {
          st.busy = false;
          var ok = st.jobs.filter(function (j) { return j.status === 'ready'; }).length;
          say(ok ? 'Pick your favourite.' : 'None of the cards passed our checks this time. Try a clearer, closer photo.', !ok);
        });
      }
    }

    function blockedView(r) {
      var box = el('div', null, 'ca-blocked');
      box.append(el('h3', 'We need a better photo to paint ' + st.name));
      var seen = {};
      (r.blocked || []).forEach(function (b) {
        (b.shortfall || []).forEach(function (s) { var t = typeof s === 'string' ? s : (s.need || s.message || ''); if (t && !seen[t]) { seen[t] = 1; box.append(el('p', t)); } });
      });
      if (r.tip) box.append(el('p', r.tip));
      if (!(r.blocked || []).length) {
        box.firstChild.textContent = 'No ' + occasionLabel(st.occasion) + ' cards for ' + st.name + ' yet';
        box.append(el('p', 'Pick another occasion and we will paint those instead.'));
      } else if (!Object.keys(seen).length && !r.tip) box.append(el('p', 'Try a well-lit photo where their face fills at least a tenth of the frame.'));
      box.append(btn('Add another photo', startView));
      root.replaceChildren(box, status); say('');
    }

    var grid = el('div', null, 'ca-grid');
    function makingView() {
      var head = el('div', null, 'store-head');
      head.append(el('h2', 'Painting cards of ' + st.name), el('p', 'About a minute each. They appear here as they finish.'));
      root.replaceChildren(head, grid, status); drawJobs();
    }

    function drawJobs() {
      grid.replaceChildren();
      st.jobs.forEach(function (j) {
        var tile = el('div', null, 'ca-tile ca-tile--' + j.status);
        if (j.status === 'ready') {
          var img = el('img'); img.alt = 'Card front'; img.loading = 'lazy';
          loadView(img, j.views.front);
          tile.append(img, btn('Choose this card', function () { detailView(j); }, 'ca-btn ca-btn--go'));
        } else if (j.status === 'failed') {
          tile.append(el('div', '✕', 'ca-tile__icon'), el('p', 'This one didn’t pass our checks.', 'ca-tile__msg'));
        } else {
          tile.append(el('div', null, 'ca-spinner'), el('p', STEP_LABEL[j.step] || 'Working…', 'ca-tile__msg'));
        }
        grid.append(tile);
      });
    }

    function poll(j) {
      var t0 = Date.now();
      function tick() {
        return host.get('/cardgen/jobs/' + encodeURIComponent(j.id)).then(function (r) {
          j.status = r.status; j.step = r.step;
          if (r.status === 'ready') { j.design_id = r.design_id; j.revision = r.revision; j.views = r.views; j.copy = r.copy || {}; j.product = r.product; st.product = r.product; }
          if (r.status === 'failed') j.error = r.error;
          drawJobs();
          if (r.status === 'ready' || r.status === 'failed') return;
          if (Date.now() - t0 > JOB_TIMEOUT_MS) { j.status = 'failed'; j.error = 'timed out'; drawJobs(); return; }
          return wait(POLL_MS).then(tick);
        });
      }
      return tick();
    }

    // render images can 409 for a few seconds after the job lands: retry quietly
    function loadView(img, path, tries) {
      tries = tries || 0;
      var url = host.asset(path) + '&t=' + Date.now();
      img.onerror = function () { if (tries < 20) setTimeout(function () { loadView(img, path, tries + 1); }, 2500); };
      img.src = url;
    }

    // ── step 5+6: pick, edit, buy ──────────────────────────────────────
    function viewsFor(did, rev) { var b = '/api/cards/' + did + '/r' + rev; return { front: b + '/preview', inside: b + '/inside', back: b + '/back' }; }

    // the message box on the right inside page, as fractions of the spread (card_scenes.inside fullbleed)
    var ART_MSG_BOX = { x: 0.55, y: 0.24, w: 0.40, h: 0.42 }, ART_SIG_BOX = { x: 0.62, y: 0.70, w: 0.26, h: 0.08 };
    // photo-grid inside (backend/photo_grid.inside)
    var GRID_MSG_BOX = { x: 0.57, y: 0.26, w: 0.36, h: 0.36 }, GRID_SIG_BOX = { x: 0.62, y: 0.66, w: 0.26, h: 0.09 };
    var MSG_BOX = ART_MSG_BOX, SIG_BOX = ART_SIG_BOX;

    // Live preview of typed words over a rendered inside image. Covers the printed message with
    // paper and sets the new words in a close web font; Apply makes the real render.
    function overlayFor(box, spreadW) {
      var o = el('div', null, 'ca-live'); o.hidden = true;
      var m = el('div', null, 'ca-live__msg'), g = el('div', null, 'ca-live__sig');
      o.append(m, g);
      function place(node, b) {
        // box is in spread fractions; spreadW is how many spread-widths this element spans (1 or 0.5)
        var left = spreadW === 1 ? b.x : (b.x - 0.5) * 2, width = spreadW === 1 ? b.w : b.w * 2;
        node.style.left = (left * 100) + '%'; node.style.top = (b.y * 100) + '%';
        node.style.width = (width * 100) + '%'; node.style.height = (b.h * 100) + '%';
      }
      place(m, MSG_BOX); place(g, SIG_BOX);
      if (getComputedStyle(box).position === 'static') box.classList.add('ca-livehost');
      box.append(o);
      return {
        set: function (msg, sig) {
          m.textContent = msg; g.textContent = sig; o.hidden = false;
          var hostW = box.getBoundingClientRect().width || 300, span = spreadW === 1 ? hostW : hostW * 2;
          m.style.fontSize = Math.max(8, span * MSG_BOX.w * 0.072) + 'px';
          g.style.fontSize = Math.max(7, span * SIG_BOX.w * 0.11) + 'px';
        },
        hide: function () { o.hidden = true; }
      };
    }

    // Front -> inside spread -> back as a real card opening (StPageFlip, hard covers).
    function buildBook(holder, v) {
      if (!(window.St && window.St.PageFlip)) return null;
      var w = Math.min(320, Math.max(180, Math.floor((holder.getBoundingClientRect().width || 640) / 2) - 8));
      var pages = [['front', 'hard'], ['inside-left', 'soft'], ['inside-right', 'soft'], ['back', 'hard']].map(function (p) {
        var pg = el('div', null, 'ca-page ca-page--' + p[0]); pg.setAttribute('data-density', p[1]);
        var src = p[0].indexOf('inside') === 0 ? v.inside : v[p[0]];
        // StPageFlip rewrites each page's own style.cssText every frame: the art rides on a child
        var art = el('div', null, 'ca-page__art'); art.style.backgroundImage = 'url("' + src + '")';
        pg.append(art);
        return pg;
      });
      var book = el('div', null, 'ca-book'); holder.replaceChildren(book);
      pages.forEach(function (p) { book.append(p); });
      try {
        var pf = new window.St.PageFlip(book, { width: w, height: Math.round(w * 1.4), size: 'fixed', showCover: true,
          maxShadowOpacity: 0.35, mobileScrollSupport: false, usePortrait: false, drawShadow: true, flippingTime: 900 });
        pf.loadFromHTML(pages);
        return { flip: pf, right: pages[2] };
      } catch (e) { return null; }
    }

    function detailView(j) {
      st.pick = j;
      if (j.template === 'photo_grid' || j.grid) { MSG_BOX = GRID_MSG_BOX; SIG_BOX = GRID_SIG_BOX; } else { MSG_BOX = ART_MSG_BOX; SIG_BOX = ART_SIG_BOX; }
      var head = el('div', null, 'store-head'), sub = el('p', 'Printed on card and posted.');
      head.append(el('h2', 'Your card for ' + (st.name || 'them')), sub);
      cardPrice().then(function (p) { if (p) sub.textContent = p + ', printed on card and posted.'; });
      var bookWrap = el('div', null, 'ca-bookwrap'), bookNav = el('div', null, 'ca-booknav');
      var faces = el('div', null, 'ca-faces3');
      var imgs = {};
      [['front', 'Front'], ['inside', 'Inside'], ['back', 'Back']].forEach(function (p) {
        // not lazy: these sit in a closed <details> and their load event opens the book
        var fig = el('figure', null, 'ca-face3'); var im = el('img'); im.alt = 'Card ' + p[1];
        var bx = el('div', null, 'ca-imgbox'); bx.append(im);
        fig.append(bx, el('figcaption', p[1])); faces.append(fig); imgs[p[0]] = im;
      });
      var staticLive = overlayFor(imgs.inside.parentNode, 1), bookLive = null, book = null;
      var allSides = el('details', null, 'ca-allsides'); allSides.append(el('summary', 'See all sides flat'), faces);
      function show() {
        var v = viewsFor(j.design_id, j.revision), abs = {};
        Object.keys(imgs).forEach(function (k) { loadView(imgs[k], v[k]); abs[k] = host.asset(v[k]) + '&t=' + Date.now(); });
        // the book needs the renders to exist: open it once the static front has loaded
        imgs.inside.addEventListener('load', function once() {
          imgs.inside.removeEventListener('load', once);
          if (book && book.flip) { try { book.flip.destroy(); } catch (e) {} }
          book = buildBook(bookWrap, abs);
          if (book) {
            bookLive = overlayFor(book.right, 0.5); allSides.open = false; bookNav.hidden = false;
          } else { allSides.open = true; bookNav.hidden = true; }
        });
      }
      bookNav.hidden = true;
      bookNav.append(btn('Open the card', function () { if (book) book.flip.flipNext(); }, 'ca-btn ca-btn--ghost'),
        btn('Close', function () { if (book) book.flip.flip(0); }, 'ca-btn ca-btn--ghost'));
      show();
      var saved = { msg: (j.copy && (j.copy.inside || j.copy.inside_message)) || '', sig: (j.copy && j.copy.sender) || '' };
      var msg = el('textarea'); msg.maxLength = 240; msg.rows = 4; msg.value = saved.msg;
      var sig = el('input'); sig.maxLength = 40; sig.placeholder = 'Love, Tom'; sig.value = saved.sig;
      function preview() {
        var dirty = msg.value.trim() !== saved.msg || sig.value.trim() !== saved.sig;
        [staticLive, bookLive].forEach(function (l) { if (!l) return; if (dirty) l.set(msg.value.trim(), sig.value.trim()); else l.hide(); });
        apply.disabled = !dirty || st.busy;
        if (dirty) say('Preview only. Press Apply to set it on the card.');
      }
      msg.addEventListener('input', preview); sig.addEventListener('input', preview);
      if (!saved.msg && !saved.sig) host.get('/cards/designs/' + j.design_id).then(function (r) {
        var sp = (r.design && r.design.spec) || {};
        saved = { msg: ((sp.inside || {}).right || {}).message || sp.inside_message || '', sig: sp.sender || '' };
        if (!msg.value) msg.value = saved.msg; if (!sig.value) sig.value = saved.sig; preview();
      }).catch(function () {});
      var apply = btn('Apply', function () {
        if (st.busy) return; st.busy = true; apply.disabled = true;
        editCopy(j, msg.value.trim(), sig.value.trim()).then(function () {
          saved = { msg: msg.value.trim(), sig: sig.value.trim() };
          [staticLive, bookLive].forEach(function (l) { if (l) l.hide(); });
          show(); say('Message set on the card.');
        }).catch(fail).then(function () { st.busy = false; preview(); });
      }, 'ca-btn ca-btn--ghost');
      apply.disabled = true;
      var buy = btn('Buy this card', function () {
        if (st.busy) return; st.busy = true; buy.disabled = true;
        checkout(j).catch(fail).then(function () { st.busy = false; buy.disabled = false; });
      }, 'ca-btn ca-btn--go');
      cardPrice().then(function (p) { if (p) buy.textContent = 'Buy this card, ' + p; });
      var back = btn(st.jobs.length ? '← See the other cards' : '← Start again', function () { if (st.jobs.length) { makingView(); say('Pick your favourite.'); } else startView(); }, 'ca-btn ca-btn--ghost');
      var edit = el('div', null, 'ca-form');
      var gridBox = null;
      if (j.template === 'photo_grid' || j.grid) {
        gridBox = el('div', null, 'ca-form ca-gridctl');
        function run(change) {
          if (st.busy) return; st.busy = true;
          changeGrid(j, change).then(function (r) { show(); say((r.selection && r.selection.summary) || 'Card updated.'); drawGrid(); })
            .catch(fail).then(function () { st.busy = false; });
        }
        function drawGrid() {
          gridBox.replaceChildren();
          var counts = el('div', null, 'ca-row');
          GRID_CHOICES.forEach(function (g) {
            var b = btn(g[1], function () { run({ photos: parseInt(g[0], 10) }); }, 'ca-btn ca-btn--ghost');
            b.disabled = String(j.grid) === g[0]; counts.append(b);
          });
          var styles = el('select');
          STYLE_CHOICES.slice(1).forEach(function (g) { var o = new Option(g[1], g[0]); o.selected = g[0] === j.style; styles.append(o); });
          styles.addEventListener('change', function () { run({ style: styles.value }); });
          var swaps = el('div', null, 'ca-row');
          for (var i = 1; i <= (j.grid || 0); i++) (function (n) {
            swaps.append(btn('Swap photo ' + n, function () { run({ swap: [n] }); }, 'ca-btn ca-btn--ghost'));
          })(i);
          gridBox.append(field('Photos on the front', counts), field('Lettering', styles), field('Not keen on one?', swaps));
        }
        drawGrid();
      }
      edit.append(field('Inside message (printed as typed)', msg), field('Signed', sig), apply, buy);
      root.replaceChildren(head, bookWrap, bookNav, allSides);
      if (gridBox) root.append(gridBox);
      root.append(edit, back, status); mount(); say('');
    }

    function renderAndWait(did, rev, kind) {
      return host.post('/cards/' + did + '/render', { revision: rev, kind: kind }).then(function (r) {
        var job = r.job || {}, t0 = Date.now();
        function tick() {
          if (job.status === 'ready') return job;
          if (job.status === 'failed') throw new Error('The ' + kind + ' render failed. Please try again.');
          if (Date.now() - t0 > 180000) throw new Error('The ' + kind + ' render is taking too long.');
          return wait(2000).then(function () { return host.get('/cards/jobs/' + job.id); }).then(function (x) { job = x.job || {}; return tick(); });
        }
        return tick();
      });
    }

    // words only: the art is untouched, a new revision is rendered
    function editCopy(j, message, signature) {
      say('Updating the message…');
      return host.get('/cards/designs/' + j.design_id).then(function (cur) {
        var d = cur.design, spec = Object.assign({}, d.spec || {});
        if (message) {
          spec.inside_message = message.slice(0, 240);
          var inner = Object.assign({}, spec.inside || {}), right = Object.assign({}, inner.right || {});
          right.message = spec.inside_message; inner.right = right; spec.inside = inner;
        }
        if (signature) spec.sender = signature.slice(0, 40);
        return host.post('/cards/designs', { id: j.design_id, expected_revision: d.revision, spec: spec });
      }).then(function (saved) {
        j.revision = saved.design.revision; j.copy = Object.assign({}, j.copy, { inside: message, sender: signature });
        return renderAndWait(j.design_id, j.revision, 'preview');
      });
    }

    function checkout(j) {
      say('Preparing the print file…');
      return renderAndWait(j.design_id, j.revision, 'export').then(function () {
        say('Opening checkout…');
        return host.post('/cards/' + j.design_id + '/checkout', { revision: j.revision, qty: 1, idempotency_key: idem('cards-' + j.design_id + '-r' + j.revision) });
      }).then(function (r) {
        if (r.checkout_url) { window.location.href = r.checkout_url; return; }
        throw new Error('Checkout is unavailable right now. Your card is saved.');
      });
    }

    // deep link /cards/<design_id>[/r<rev>]
    function openDesign(did, rev) {
      var p0 = host.ready ? Promise.resolve(host.ready()) : Promise.resolve();
      return p0.then(function () { return openDesign2(did, rev); });
    }
    function openDesign2(did, rev) {
      var p = rev ? Promise.resolve(rev) : host.get('/cards/designs/' + did).then(function (r) { return r.design.revision; });
      return host.get('/cards/designs/' + did).then(function (cur) {
        var sp = (cur.design && cur.design.spec) || {};
        return p.then(function (r) { detailView({ design_id: did, revision: r, copy: {}, views: viewsFor(did, r), product: st.product,
          template: sp.template, grid: sp.grid, style: sp.grid_style }); });
      });
    }

    return {
      open: function () {
        if (root.childNodes.length) return mount();
        var r = host.ready ? Promise.resolve(host.ready()) : Promise.resolve();
        r.then(startView, function (e) { startView(); fail(e); });
      },
      openDesign: openDesign,
      restart: startView
    };
  };
})();
