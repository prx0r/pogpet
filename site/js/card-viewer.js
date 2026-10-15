/* OddHobb card/product viewer: arrows left/right, card in the middle.
 * Data-driven: items = [{id, revision, title, price, views:{front,inside,back}, checkout}]
 * Works for PIL designs, cardgen jobs, and products later. No deps. */
(function () {
  'use strict';

  var VIEWS = [['front', 'Front'], ['inside', 'Inside'], ['back', 'Back']];

  function el(tag, text, cls) {
    var n = document.createElement(tag);
    if (text != null) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  }

  function viewUrls(host, item) {
    var b = '/cards/' + item.id + '/r' + item.revision;
    return { front: host.asset(b + '/preview'), inside: host.asset(b + '/inside'), back: host.asset(b + '/back') };
  }

  window.OddHobbCardViewer = {
    /* Mount a finished-cards carousel. Returns {refresh(), destroy()}.
     * host: {get, post, asset} like the card studio host. */
    mountSaved: function (container, host, opts) {
      opts = opts || {};
      var root = el('section', null, 'cv cv--hidden');
      root.setAttribute('aria-label', 'Your finished cards');
      container.appendChild(root);
      var state = { items: [], idx: 0, view: 'front', destroyed: false };

      function say(msg) {
        var n = root.querySelector('.cv-note');
        if (n) n.textContent = msg || '';
      }

      function paint() {
        root.replaceChildren();
        if (!state.items.length) { root.classList.add('cv--hidden'); return; }
        root.classList.remove('cv--hidden');
        var head = el('div', null, 'cv-head');
        head.append(el('h3', 'Your finished cards'), el('p', 'Tap the arrows or swipe. Pick a card, check inside, buy.'));
        root.append(head);

        var wrap = el('div', null, 'cv-stage-wrap');
        var prev = el('button', '‹', 'cv-arrow'); prev.type = 'button'; prev.setAttribute('aria-label', 'Previous card');
        var next = el('button', '›', 'cv-arrow'); next.type = 'button'; next.setAttribute('aria-label', 'Next card');
        var viewport = el('div', null, 'cv-track-view');
        viewport.tabIndex = 0;
        viewport.setAttribute('role', 'region');
        viewport.setAttribute('aria-roledescription', 'carousel');
        viewport.setAttribute('aria-label', 'Finished cards');
        var track = el('ol', null, 'cv-track');
        viewport.append(track);

        state.items.forEach(function (item, i) {
          var li = el('li', null, 'cv-slide');
          li.setAttribute('aria-label', (i + 1) + ' of ' + state.items.length + ': ' + item.title);
          var img = el('img');
          img.alt = item.title + ' — ' + state.view;
          img.loading = i === state.idx ? 'eager' : 'lazy';
          img.draggable = false;
          var url = item.views[state.view];
          img.onerror = function () {
            if (!img.dataset.fbk && state.view !== 'front' && item.views.front) {
              img.dataset.fbk = '1'; img.src = item.views.front; return;
            }
            li.replaceChildren(el('p', 'Still rendering — check back in a minute.', 'cv-slide--missing'));
          };
          img.src = url;
          li.append(img);
          track.append(li);
        });

        function go(i) {
          state.idx = (i + state.items.length) % state.items.length;
          paint();
          var first = track.children[state.idx];
          if (first) { var im = first.querySelector('img'); if (im) im.focus && im.focus(); }
        }
        prev.addEventListener('click', function () { go(state.idx - 1); });
        next.addEventListener('click', function () { go(state.idx + 1); });
        viewport.addEventListener('keydown', function (e) {
          if (e.key === 'ArrowLeft') { e.preventDefault(); go(state.idx - 1); }
          else if (e.key === 'ArrowRight') { e.preventDefault(); go(state.idx + 1); }
        });
        var touchX = null;
        viewport.addEventListener('touchstart', function (e) {
          touchX = e.changedTouches[0].clientX;
        }, { passive: true });
        viewport.addEventListener('touchend', function (e) {
          if (touchX == null) return;
          var dx = e.changedTouches[0].clientX - touchX;
          touchX = null;
          if (Math.abs(dx) < 24) return;
          go(state.idx + (dx < 0 ? 1 : -1));
        }, { passive: true });

        wrap.append(prev, viewport, next);
        root.append(wrap);

        var item = state.items[state.idx];
        track.style.transform = 'translateX(-' + (state.idx * 100) + '%)';

        var meta = el('div', null, 'cv-meta');
        meta.append(el('span', item.title, 'cv-title'), el('span', item.price || '', 'cv-price'));
        root.append(meta);

        var tabs = el('div', null, 'cv-views');
        VIEWS.forEach(function (v) {
          var b = el('button', v[1], 'cv-view-btn');
          b.type = 'button';
          b.setAttribute('aria-pressed', state.view === v[0] ? 'true' : 'false');
          b.addEventListener('click', function () { state.view = v[0]; paint(); });
          tabs.append(b);
        });
        root.append(tabs);

        var dots = el('div', null, 'cv-dots');
        state.items.forEach(function (it, i) {
          var d = el('button', null, 'cv-dot');
          d.type = 'button';
          d.setAttribute('aria-label', 'Show card ' + (i + 1) + ': ' + it.title);
          d.setAttribute('aria-current', i === state.idx ? 'true' : 'false');
          d.addEventListener('click', function () { go(i); });
          dots.append(d);
        });
        root.append(dots);

        var cta = el('div', null, 'cv-cta');
        var openBtn = el('button', 'Open the card', 'cv-view-btn');
        openBtn.type = 'button';
        openBtn.addEventListener('click', function () { openBook(item); });
        cta.append(openBtn);
        var buy = el('button', 'Buy this card — ' + (item.price || ''), 'cv-buy');
        buy.type = 'button';
        buy.addEventListener('click', function () {
          buy.disabled = true; say('Making your checkout…');
          host.post('/cards/' + item.id + '/checkout', { revision: item.revision }).then(function (r) {
            if (r.checkout_url) window.location.href = r.checkout_url;
            else { say(r.product_url ? 'Done: ' + r.product_url : 'Checkout ready.'); buy.disabled = false; }
          }).catch(function (e) { say((e && e.message) || 'Checkout failed.', true); buy.disabled = false; });
        });
        cta.append(buy);
        root.append(cta);
        root.append(el('p', '', 'cv-note'));
      }

      /* Page-turn: front (hard cover) -> inside spread -> back (hard cover).
       * StPageFlip, vendored locally, no deps. Falls back to tabs if missing. */
      function openBook(item) {
        if (!window.St || !window.St.PageFlip) { state.view = 'inside'; paint(); return; }
        var stage = root.querySelector('.cv-track-view');
        if (!stage) return;
        stage.innerHTML = '';
        var book = el('div', null, 'cv-book');
        stage.appendChild(book);
        try {
          var flip = new window.St.PageFlip(book, {
            width: 300, height: 420, showCover: true,
            flippingTime: 800, usePortrait: true, maxShadowOpacity: 0.6
          });
          flip.loadFromImages([item.views.front, item.views.inside, item.views.back]);
        } catch (e) {
          state.view = 'inside'; paint();
        }
        say('Tap the corner or swipe to turn the page.');
      }

      function refresh() {        if (state.destroyed) return Promise.resolve();
        return host.get('/cards/designs').then(function (d) {
          var items = (d.designs || []).map(function (x) {
            var b = '/cards/' + x.id + '/r' + x.revision;
            return {
              id: x.id, revision: x.revision,
              title: ((x.spec || {}).headline) || 'Untitled card',
              price: (x.product && x.product.price_label) || opts.price || '',
              views: {
                front: host.asset(b + '/preview'),
                inside: host.asset(b + '/inside'),
                back: host.asset(b + '/back')
              }
            };
          });
          state.items = items;
          if (state.idx >= items.length) state.idx = 0;
          paint();
        }).catch(function () { /* empty shelf: stay hidden */ });
      }

      function destroy() { state.destroyed = true; root.remove(); }

      refresh();
      return { refresh: refresh, destroy: destroy };
    }
  };
})();
