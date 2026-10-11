/* OddHobb /cards: upload a photo, get cards made automatically.
 *
 * The one customer flow for paper cards, on the canonical cardgen engine:
 *   1 who + occasion (+ relationship, one or two interests for the joke)
 *   2 upload 1-3 photos -> faces detected on upload -> tap their face if several
 *   3 POST /cardgen/recommend -> the templates these photos can make
 *   4 POST /cardgen/make for the top 4, poll /cardgen/jobs/<id> (step by step)
 *   5 pick one -> front / inside / back, edit the inside message (live type)
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
    var st = { subject: null, photos: [], occasion: 'birthday', relationship: '', interests: [], name: '', jobs: [], pick: null, busy: false };
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
      head.append(el('h2', 'Cards that star your people'), el('p', 'Pick someone — we paint up to four cards from their saved photos with a joke that fits, and you pick one. Printed and posted.'));
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
        el('p', 'A real birthday card we made: painted front, message inside, clean back. Pick someone below and we paint theirs.'),
        exRow);
      var form = el('div', null, 'ca-form');
      var who = el('select'); who.append(new Option('Someone new', ''));
      var name = el('input'); name.maxLength = 60; name.placeholder = 'Dad, Mum, Biscuit the dog…';
      var rel = el('input'); rel.maxLength = 40; rel.placeholder = 'dad, best friend, our dog';
      var interests = el('input'); interests.maxLength = 120; interests.placeholder = 'golf, Tesla, terrible puns';
      var occ = el('select'); OCCASIONS.forEach(function (o) { occ.append(new Option(o[1], o[0])); });
      var kind = el('select'); kind.append(new Option('Person', 'person'), new Option('Pet', 'pet'));
      var file = el('input'); file.type = 'file'; file.accept = 'image/jpeg,image/png,image/webp'; file.multiple = true;
      var thumbs = el('div', null, 'ca-thumbs');
      var savedNote = el('p', '', 'ca-status');
      var newOnly = el('div', null, 'ca-new'); newOnly.append(field('Their name', name), field('Person or pet', kind));
      var identity = el('div', null, 'ca-identity');
      var whoField = field('Who is it for?', who);
      var relField = field('Who are they to you?', rel);
      var intField = field('What are they into? (for the joke)', interests);
      var photoField = field('Add photos (optional if they’re already below)', file);
      identity.append(whoField, newOnly, relField, intField, photoField);
      var forLine = el('p', '', 'ca-forline');
      var changeBtn = btn('Change person', function () {
        who.value = ''; newOnly.hidden = false; identity.hidden = false;
        forLine.hidden = true; savedNote.textContent = '';
      }, 'ca-btn ca-btn--ghost');
      forLine.hidden = true;
      function pickPerson(id) {
        who.value = id;
        newOnly.hidden = true;
        var s = (st.library && st.library.subjects || []).find(function (x) { return x.id === id; });
        if (s) {
          rel.value = s.relationship || ''; interests.value = (s.interests || []).join(', ');
          identity.hidden = true;
          forLine.hidden = false;
          forLine.textContent = 'For ' + s.name +
            (s.relationship ? ' · ' + s.relationship : '') +
            (s.interests && s.interests.length ? ' · ' + s.interests.slice(0, 3).join(', ') : '') +
            (s.photo_count ? ' · ' + s.photo_count + ' saved photos' : '');
          savedNote.textContent = 'Photos inherited — just pick the occasion and hit the button.';
        }
      }
      who.addEventListener('change', function () {
        newOnly.hidden = !!who.value;
        if (!who.value) {
          identity.hidden = false; forLine.hidden = true; savedNote.textContent = '';
          return;
        }
        pickPerson(who.value);
      });
      file.addEventListener('change', function () {
        thumbs.replaceChildren();
        Array.prototype.slice.call(file.files, 0, 3).forEach(function (f) { var i = el('img'); i.alt = ''; i.src = URL.createObjectURL(f); thumbs.append(i); });
      });
      var go = btn('Make my cards', function () {
        if (st.busy) return;
        var files = Array.prototype.slice.call(file.files || [], 0, 3);
        if (!who.value && !name.value.trim()) return say('Tell us their name first.', true);
        if (!who.value && !files.length) return say('Add at least one clear photo of them.', true);
        st.occasion = occ.value; st.relationship = rel.value.trim();
        st.interests = interests.value.split(',').map(function (s) { return s.trim(); }).filter(Boolean).slice(0, 6);
        st.busy = true; go.disabled = true;
        prepare(who.value, name.value.trim(), kind.value, files).then(recommend).catch(fail).then(function () { go.disabled = false; });
      }, 'ca-btn ca-btn--go');
      form.append(identity, forLine, changeBtn, field('Occasion', occ),
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

    function detailView(j) {
      st.pick = j;
      var head = el('div', null, 'store-head');
      head.append(el('h2', 'Your card for ' + (st.name || 'them')), el('p', ((j.product && j.product.price) ? j.product.price + ', ' : '') + 'printed on card and posted.'));
      var faces = el('div', null, 'ca-faces3');
      var imgs = {};
      [['front', 'Front'], ['inside', 'Inside'], ['back', 'Back']].forEach(function (p) {
        var fig = el('figure', null, 'ca-face3'); var im = el('img'); im.alt = 'Card ' + p[1]; im.loading = 'lazy';
        fig.append(im, el('figcaption', p[1])); faces.append(fig); imgs[p[0]] = im;
      });
      function show() { var v = viewsFor(j.design_id, j.revision); Object.keys(imgs).forEach(function (k) { loadView(imgs[k], v[k]); }); }
      show();
      var msg = el('textarea'); msg.maxLength = 240; msg.rows = 4; msg.value = (j.copy && (j.copy.inside || j.copy.inside_message)) || '';
      var sig = el('input'); sig.maxLength = 40; sig.placeholder = 'Love, Tom';
      var saveMsg = btn('Update the message', function () {
        if (st.busy) return; st.busy = true; saveMsg.disabled = true;
        editCopy(j, msg.value.trim(), sig.value.trim()).then(function () { show(); say('Message updated.'); })
          .catch(fail).then(function () { st.busy = false; saveMsg.disabled = false; });
      }, 'ca-btn ca-btn--ghost');
      var buy = btn('Buy this card' + (j.product && j.product.price ? ', ' + j.product.price : ''), function () {
        if (st.busy) return; st.busy = true; buy.disabled = true;
        checkout(j).catch(fail).then(function () { st.busy = false; buy.disabled = false; });
      }, 'ca-btn ca-btn--go');
      var back = btn('← See the other cards', function () { if (st.jobs.length) { makingView(); say('Pick your favourite.'); } else startView(); }, 'ca-btn ca-btn--ghost');
      var edit = el('div', null, 'ca-form');
      edit.append(field('Inside message (printed as typed)', msg), field('Signed', sig), saveMsg, buy);
      root.replaceChildren(head, faces, edit, back, status); mount(); say('');
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
        j.revision = saved.design.revision; j.copy = Object.assign({}, j.copy, { inside: message });
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
      return p.then(function (r) { detailView({ design_id: did, revision: r, copy: {}, views: viewsFor(did, r), product: st.product }); });
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
