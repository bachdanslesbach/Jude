(function () {
  'use strict';
  var S = __STRINGS__;
  var body = document.body;
  // The per-origin secret. It arrived once, on the one-shot landing page, and
  // lives in sessionStorage — scoped to scheme, host AND port, unlike the
  // cookie. Every /api/* call carries it; without it this tab shows nothing.
  var sessionKey = body.getAttribute('data-session-key') || 'jude_csrf';
  var csrf = null;
  try { csrf = sessionStorage.getItem(sessionKey); } catch (e) { csrf = null; }
  var reviewId = '';
  var TERMINAL = { released: 1, cancelled: 1, expired: 1, failed: 1 };
  var failures = 0;
  var busy = false;
  var lastInput = Date.now();
  var lastHeartbeat = 0;
  function $(sel) { return document.querySelector(sel); }
  function screen() { return $('section.screen'); }
  function showBanner(text) { var b = $('#banner'); b.textContent = text; b.classList.remove('hidden'); }
  function hideBanner() { $('#banner').classList.add('hidden'); }
  function showError(key) {
    var e = $('#error'); if (!e) return;
    e.textContent = S['ui.error.' + key] || S['ui.error.generic'];
    e.classList.remove('hidden');
  }
  function api(method, path, data, raw, extra) {
    var headers = { 'X-Jude-CSRF': csrf || '' };
    if (method === 'POST') headers['Content-Type'] = raw ? 'application/octet-stream' : 'application/json';
    if (extra) { for (var k in extra) headers[k] = extra[k]; }
    return fetch(path, {
      method: method, headers: headers, credentials: 'same-origin', cache: 'no-store',
      body: method === 'POST' ? (raw ? data : JSON.stringify(data || {})) : undefined
    });
  }
  function fmt(seconds) {
    var m = Math.floor(seconds / 60); var s = seconds % 60;
    return m + ':' + (s < 10 ? '0' : '') + s;
  }
  // ----- text read: the leaving text was scrolled to its end (or needs no scrolling) -----
  function wireLeaving() {
    var pre = $('#leaving'); if (!pre) return;
    function check() { if (pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 2) pre.setAttribute('data-text-read', '1'); }
    pre.addEventListener('scroll', check);
    check();
  }
  function wireApprove() {
    var box = $('#attest'); var btn = $('[data-action="approve"]');
    if (box && btn) { btn.disabled = !box.checked; box.addEventListener('change', function () { btn.disabled = !box.checked; }); }
    wireLeaving();
  }
  // Partial swap: same screen, new text — keep the lawyer's scroll position.
  function swap(html) {
    var cur = screen();
    var tmp = document.createElement('div'); tmp.innerHTML = html;
    var next = tmp.querySelector('section.screen');
    if (cur && next && cur.getAttribute('data-status') === 'awaiting_review' &&
        next.getAttribute('data-status') === 'awaiting_review') {
      var oldPre = $('#leaving'); var top = oldPre ? oldPre.scrollTop : 0;
      var showOriginal = $('#original') && !$('#original').classList.contains('hidden');
      var showInv = cur.classList.contains('show-inv');
      ['table.entities', '#leaving', '#original', '.counts', '.risk', 'p.sha', '.languages'].forEach(function (sel) {
        var a = cur.querySelector(sel); var b = next.querySelector(sel);
        if (a && b) a.replaceWith(b); else if (a && !b) a.remove();
      });
      cur.setAttribute('data-sha256', next.getAttribute('data-sha256') || '');
      var box = $('#attest'); var btn = $('[data-action="approve"]');
      if (box) box.checked = false;
      if (btn) btn.disabled = true;
      var pre = $('#leaving'); if (pre) pre.scrollTop = top;
      if (showOriginal) { $('#leaving').classList.add('hidden'); $('#original').classList.remove('hidden'); }
      if (showInv) cur.classList.add('show-inv');
      wireLeaving();
      return;
    }
    $('#screen').innerHTML = html;
    wireApprove();
  }
  function refresh() {
    if (!reviewId) return Promise.resolve();
    return api('GET', '/api/r/' + reviewId + '/fragment')
      .then(function (r) { if (!r.ok) throw new Error('fragment'); return r.text(); })
      .then(swap);
  }
  function refreshAnswers() {
    var box = $('#answers'); if (!box) return Promise.resolve();
    return api('GET', '/api/r/' + reviewId + '/answers')
      .then(function (r) { if (!r.ok) throw new Error('answers'); return r.text(); })
      .then(function (html) { box.innerHTML = html; });
  }
  function setStatusLine(st) {
    var line = $('#status-line'); if (!line) return;
    if (st.status === 'released') line.textContent = S['ui.status.handed_once'] + ' #' + st.approval_id + '.';
    else line.textContent = S['ui.nothing_left'];
  }
  function setCountdown(st) {
    var cd = $('#countdown'); var val = $('#countdown-value');
    if (cd && val) {
      if (typeof st.expires_in === 'number' && st.expires_in < 300 && !TERMINAL[st.status] && st.status !== 'approved') {
        val.textContent = fmt(st.expires_in); cd.classList.remove('hidden');
      } else { cd.classList.add('hidden'); }
    }
    var ac = $('#approved-countdown');
    if (ac && st.status === 'approved' && typeof st.expires_in === 'number') ac.textContent = '(' + fmt(st.expires_in) + ')';
  }
  // The shell carries no review: /api/current says which one to show. When
  // the current review changes (a new one after a closed one), this tab
  // follows it without a reload.
  function pollCurrent() {
    return api('GET', '/api/current')
      .then(function (r) { if (!r.ok) throw new Error('current'); return r.json(); })
      .then(function (cur) {
        failures = 0; hideBanner();
        if (cur.review_id && cur.review_id !== reviewId) { reviewId = cur.review_id; return refresh(); }
        if (!cur.review_id) setStatusLine({ status: 'none' });
      })
      .catch(function () { failures += 1; if (failures >= 3) showBanner(S['banner.server_gone']); });
  }
  function pollState() {
    if (!reviewId) return Promise.resolve();
    return api('GET', '/api/r/' + reviewId + '/state')
      .then(function (r) { if (!r.ok) throw new Error('state'); return r.json(); })
      .then(function (st) {
        failures = 0; hideBanner();
        setStatusLine(st); setCountdown(st);
        var cur = screen();
        var curStatus = cur ? cur.getAttribute('data-status') : null;
        var curSha = cur ? cur.getAttribute('data-sha256') : null;
        var curPhase = cur ? cur.getAttribute('data-phase') : null;
        if (curStatus !== st.status || (st.sha256 && curSha !== st.sha256)) return refresh();
        if (st.status === 'preparing' && st.phase && curPhase !== st.phase) return refresh();
        if (st.status === 'released') {
          var shown = cur ? parseInt(cur.getAttribute('data-answers') || '0', 10) : 0;
          if (st.answers !== shown) { cur.setAttribute('data-answers', String(st.answers)); return refreshAnswers(); }
        }
      })
      .catch(function () {
        failures += 1;
        // Three consecutive failures: the server is gone (or this tab is stale).
        if (failures >= 3) showBanner(S['banner.server_gone']);
      });
  }
  function poll() {
    if (busy || !csrf) return;
    var cur = screen();
    var curStatus = cur ? cur.getAttribute('data-status') : 'none';
    if (!reviewId || TERMINAL[curStatus]) {
      pollCurrent().then(function () { if (reviewId) return pollState(); });
      return;
    }
    pollState();
  }
  // ----- heartbeat: real input in a visible tab, at most every 30 s -----
  function noteInput() { lastInput = Date.now(); }
  ['pointermove', 'keydown', 'scroll', 'click'].forEach(function (ev) { document.addEventListener(ev, noteInput, true); });
  function heartbeat() {
    if (!reviewId || !csrf) return;
    var cur = screen(); var st = cur ? cur.getAttribute('data-status') : 'none';
    if (TERMINAL[st] || st === 'approved') return;
    if (document.visibilityState !== 'visible') return;
    var now = Date.now();
    if (now - lastInput > 60000 || now - lastHeartbeat < 30000) return;
    lastHeartbeat = now;
    api('POST', '/api/r/' + reviewId + '/heartbeat', {}).catch(function () {});
  }
  function handleFailure(r) {
    return r.json().then(function (j) {
      if (r.status === 409) {
        showError(j.error === 'text_changed' ? 'text_changed' : 'stale_page');
        return refresh();
      }
      showError(j.error || 'generic');
    }, function () { showError('generic'); });
  }
  function onClick(ev) {
    var b = ev.target.closest('[data-action]'); if (!b) return;
    var action = b.getAttribute('data-action');
    var base = '/api/r/' + reviewId;
    if (action === 'lang') {
      api('POST', '/api/lang', { lang: b.getAttribute('data-lang') }).then(function () { location.reload(); });
      return;
    }
    if (action === 'copy') {
      var text = b.getAttribute('data-copy');
      if (navigator.clipboard) navigator.clipboard.writeText(text);
      return;
    }
    if (action === 'copy-answer') {
      var target = document.getElementById(b.getAttribute('data-target'));
      if (target && navigator.clipboard) navigator.clipboard.writeText(target.textContent);
      return;
    }
    if (action === 'toggle-original') {
      var leaving = $('#leaving'); var original = $('#original');
      if (!leaving || !original) return;
      var showingOriginal = !original.classList.contains('hidden');
      leaving.classList.toggle('hidden', !showingOriginal);
      original.classList.toggle('hidden', showingOriginal);
      b.textContent = showingOriginal ? b.getAttribute('data-label-off') : b.getAttribute('data-label-on');
      return;
    }
    if (action === 'toggle-invisible') {
      var sec = screen(); if (!sec) return;
      var on = sec.classList.toggle('show-inv');
      b.textContent = on ? b.getAttribute('data-label-on') : b.getAttribute('data-label-off');
      return;
    }
    if (!reviewId) return;
    busy = true;
    var p;
    if (action === 'choose-matter') {
      var sel = $('#matter');
      p = api('POST', base + '/matter', { matter_id: sel ? sel.value : '' })
        .then(function (r) { if (r.ok) return r.text().then(swap); return handleFailure(r); });
    } else if (action === 'upload') {
      var input = $('#file');
      if (!input || !input.files || !input.files[0]) { busy = false; return; }
      var f = input.files[0];
      var dot = f.name.lastIndexOf('.');
      var suffix = dot >= 0 ? f.name.slice(dot).toLowerCase() : '';
      p = api('POST', base + '/file', f, true, { 'X-Jude-Suffix': suffix })
        .then(function (r) { if (r.ok) return refresh(); return handleFailure(r); });
    } else if (action === 'decide') {
      p = api('POST', base + '/decide', { entity_id: parseInt(b.getAttribute('data-entity'), 10), action: b.getAttribute('data-decision') })
        .then(function (r) { if (r.ok) return r.text().then(swap); return handleFailure(r); });
    } else if (action === 'mark') {
      var surf = $('#mark-surface'); var kind = $('#mark-type');
      p = api('POST', base + '/mark', { surface: surf ? surf.value : '', type: kind ? kind.value : 'OTHER' })
        .then(function (r) { if (r.ok) return r.text().then(swap); return handleFailure(r); });
    } else if (action === 'approve') {
      var sec2 = screen(); var box = $('#attest'); var pre = $('#leaving');
      p = api('POST', base + '/approve', {
        sha256: sec2 ? sec2.getAttribute('data-sha256') : '',
        attest: !!(box && box.checked),
        text_read: !!(pre && pre.getAttribute('data-text-read') === '1')
      }).then(function (r) { if (r.ok) return refresh(); return handleFailure(r); });
    } else if (action === 'cancel') {
      p = api('POST', base + '/cancel', {})
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) {
          return refresh().then(function () {
            // A withdrawal that arrived after the release: say so, once.
            if (j && j.status === 'released') { var tl = $('#too-late'); if (tl) tl.classList.remove('hidden'); }
          });
        });
    } else {
      busy = false; return;
    }
    p.catch(function () { showError('generic'); }).then(function () { busy = false; });
  }
  document.addEventListener('click', onClick);
  wireApprove();
  if (!csrf) {
    // No per-origin secret: this tab was not opened through a one-shot URL
    // (or the browser dropped its session storage). Nothing is fetched.
    showBanner(S['ui.no_session']);
    return;
  }
  poll();
  setInterval(poll, 3000);
  setInterval(heartbeat, 5000);
})();
