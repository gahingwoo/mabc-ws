/*
 * Copyright (C) 2026 Jiaxing Hu <gahing@gahingwoo.com>
 *
 * This program is free software; you can redistribute it and/or modify it under
 * the terms of the GNU General Public License version 2 as published by the
 * Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * this program; if not, see <https://www.gnu.org/licenses/>.
 */
// Shared behaviour: theme toggle, sidebar, the section-in-view marker on the
// rail, and back to top. Adapted from gahingwoo.com, which runs the same shell.

(function () {
  var root = document.documentElement;
  // The page is PatternFly's app shell, so the thing that scrolls is the main
  // container, not the window. Everything below watches and drives that.
  // What scrolls depends on the width: the shell's main area on a large
  // screen, the document itself below xl, where the browser's own gestures
  // need it. Everything below asks rather than assumes.
  var pageMain = document.querySelector('.pf-v6-c-page__main');
  var appShell = window.matchMedia('(min-width: 75rem)');
  function scroller() { return (appShell.matches && pageMain) ? pageMain : document.scrollingElement; }
  function scrollTop() { return scroller().scrollTop; }
  function viewportTop() { return (appShell.matches && pageMain) ? pageMain.getBoundingClientRect().top : 0; }
  // Scroll does not bubble, so this listens in the capture phase and catches
  // it from whichever element is doing the scrolling.
  function onScroll(fn) { document.addEventListener('scroll', fn, { passive: true, capture: true }); }

  // The same browser feature that carries one page into the next also covers
  // state changes within a page: it snapshots before and after and morphs
  // between them, which is how the sidebar and the theme change without a
  // jump. Where it is missing, or the reader asks for less motion, the change
  // just happens.
  var lessMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  function withTransition(fn) {
    if (document.startViewTransition && !lessMotion.matches) document.startViewTransition(fn);
    else fn();
  }

  // Where an external link opens. In the content these are citations: the
  // reader's task stays on this page and they come back for the next one, so
  // those open in a new tab. In the sidebar they are navigation, where
  // leaving is the intent, so those are left alone. Either way the glyph
  // added in site.css says the link goes elsewhere.
  Array.prototype.forEach.call(
    document.querySelectorAll('.pf-v6-c-page__main a[href^="http"]'),
    function (a) {
      if (a.href.indexOf('https://www.mabc.org.nz') === 0) return;
      a.target = '_blank';
      a.rel = a.rel ? a.rel + ' noopener' : 'noopener';
    }
  );

  // Theme. PatternFly 6 switches to dark with a class on <html>; the inline
  // script in each page's <head> applies the saved choice before first paint.
  var toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      withTransition(function () {
        var dark = root.classList.toggle('pf-v6-theme-dark');
        try { localStorage.setItem('theme', dark ? 'dark' : 'light'); } catch (e) {}
      });
    });
  }

  // Print (and the CV PDF, which is printed by headless Chrome) is always the
  // light theme: drop the dark class while printing and put it back after.
  var wasDark = false;
  window.addEventListener('beforeprint', function () {
    wasDark = root.classList.contains('pf-v6-theme-dark');
    root.classList.remove('pf-v6-theme-dark');
  });
  window.addEventListener('afterprint', function () {
    if (wasDark) root.classList.add('pf-v6-theme-dark');
  });

  // Sidebar. PatternFly shows it from xl and hides it below; the hamburger
  // slides it in and out. A choice inside it closes it on small screens.
  var sidebar = document.getElementById('site-sidebar');
  var navToggle = document.getElementById('nav-toggle');
  var wide = window.matchMedia('(min-width: 75rem)');
  var backdrop = document.getElementById('site-backdrop');
  var masthead = document.querySelector('.pf-v6-c-masthead');
  // Below xl the panel is pinned under the masthead, whose height the CSS
  // cannot know on its own.
  function syncMastheadHeight() {
    if (masthead) document.documentElement.style.setProperty('--masthead-h', masthead.offsetHeight + 'px');
  }
  syncMastheadHeight();
  window.addEventListener('resize', syncMastheadHeight, { passive: true });

  function setSidebar(open) {
    sidebar.classList.toggle('pf-m-expanded', open);
    // pf-m-collapsed takes the sidebar's width to zero, which is how the wide
    // layout gives the space back to the content. Below xl the panel lies
    // over the content and hides itself by sliding out, so applying it there
    // would cut that slide short.
    sidebar.classList.toggle('pf-m-collapsed', !open && wide.matches);
    navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (backdrop) {
      if (open && !wide.matches) { backdrop.hidden = false; requestAnimationFrame(function () { backdrop.classList.add('is-on'); }); }
      else {
        backdrop.classList.remove('is-on');
        if (backdrop.hidden === false) window.setTimeout(function () { if (!backdrop.classList.contains('is-on')) backdrop.hidden = true; }, 250);
      }
    }
  }
  if (sidebar && navToggle) {
    setSidebar(wide.matches);
    wide.addEventListener('change', function (e) { setSidebar(e.matches); });
    navToggle.addEventListener('click', function () {
      // From xl the sidebar is a column of the page grid, so collapsing it
      // resizes the content beside it; below xl PatternFly slides it in over
      // the content itself and needs no help.
      var open = !sidebar.classList.contains('pf-m-expanded');
      if (wide.matches) withTransition(function () { setSidebar(open); });
      else setSidebar(open);
    });
    sidebar.addEventListener('click', function (e) { if (e.target.closest('a') && !wide.matches) setSidebar(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !wide.matches) setSidebar(false); });
    // A tap beside the panel closes it. The backdrop catches most of these;
    // this also covers anything it does not, and makes the tap dismiss only,
    // rather than also following a link it landed on.
    // Opening the panel pushes a history entry, so the system back gesture
    // closes it instead of leaving the page. Closing it any other way pops
    // that entry again.
    var pushed = false;
    var baseSetSidebar = setSidebar;
    setSidebar = function (open, fromHistory) {
      baseSetSidebar(open);
      if (wide.matches) return;
      if (open && !pushed) { pushed = true; try { history.pushState({ sidebar: true }, ''); } catch (e) { pushed = false; } }
      else if (!open && pushed && !fromHistory) { pushed = false; try { history.back(); } catch (e) {} }
      else if (!open) { pushed = false; }
    };
    window.addEventListener('popstate', function () {
      if (!wide.matches && sidebar.classList.contains('pf-m-expanded')) { pushed = false; setSidebar(false, true); }
    });

    document.addEventListener('click', function (e) {
      if (wide.matches || !sidebar.classList.contains('pf-m-expanded')) return;
      if (sidebar.contains(e.target) || e.target.closest('.pf-v6-c-masthead__toggle')) return;
      e.preventDefault();
      e.stopPropagation();
      setSidebar(false);
    }, true);
  }

  // On this page: the toggle below xl, and the section in view lit on the rail.
  var jumpNav = document.getElementById('jump-nav');
  var jumpToggle = document.getElementById('jump-toggle');
  if (jumpNav && jumpToggle) {
    jumpToggle.addEventListener('click', function () {
      var open = jumpNav.classList.toggle('pf-m-expanded');
      jumpToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    jumpNav.addEventListener('click', function (e) {
      if (e.target.closest('a') && !wide.matches) {
        jumpNav.classList.remove('pf-m-expanded');
        jumpToggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // PatternFly's jump links spy on a scroll container only when one is named:
  // "Not passing a scrollableRef or scrollableSelector disables spying." The
  // stacked pages name one; the overview lays its cards out in a grid, where
  // two sections sit side by side and there is no one section the reader is
  // in, so it names none and the list is links alone.
  var jumpList = document.getElementById('jump-list');
  var spyTarget = jumpNav && jumpNav.dataset.scrollable ? document.querySelector(jumpNav.dataset.scrollable) : null;
  if (jumpList && spyTarget) {
    var items = Array.prototype.slice.call(jumpList.querySelectorAll('.pf-v6-c-jump-links__item'));
    var targets = items.map(function (li) { return document.getElementById(li.querySelector('a').getAttribute('href').slice(1)); });

    // One marker that slides, in place of the border the component draws on
    // each item; see .rail-marker in site.css.
    var marker = document.createElement('span');
    marker.className = 'rail-marker';
    marker.setAttribute('aria-hidden', 'true');
    jumpList.appendChild(marker);
    jumpNav.classList.add('has-rail-marker');
    function placeMarker(li) {
      if (!li) { marker.classList.remove('is-on'); return; }
      var link = li.querySelector('.pf-v6-c-jump-links__link');
      marker.style.height = link.offsetHeight + 'px';
      marker.style.transform = 'translateY(' + link.offsetTop + 'px)';
      marker.classList.add('is-on');
    }
    var spyTicking = false;
    function spy() {
      spyTicking = false;
      var mark = viewportTop() + 96, current = -1;
      for (var i = 0; i < targets.length; i++) {
        if (targets[i] && targets[i].getBoundingClientRect().top <= mark) current = i;
      }
      var sc = scroller();
      if (sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 4) current = targets.length - 1;
      if (current < 0) current = 0;
      items.forEach(function (li, i) {
        li.classList.toggle('pf-m-current', i === current);
        if (i === current) li.setAttribute('aria-current', 'location'); else li.removeAttribute('aria-current');
      });
      placeMarker(items[current]);
    }
    onScroll(function () {
      if (!spyTicking) { spyTicking = true; window.requestAnimationFrame(spy); }
    });
    window.addEventListener('resize', spy, { passive: true });
    spy();
  }

  // The year in the footer, so a page served next January is not stale.
  var year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());

  // The map. A cross-origin iframe begins loading with the page even when it
  // is marked lazy, and a cross-document view transition waits for the new
  // page to be ready to paint, so an always-present frame made the one
  // navigation into this page stutter. The frame is built when its placeholder
  // comes into view, which also means no request leaves for the map host
  // unless a reader actually reaches it.
  Array.prototype.forEach.call(document.querySelectorAll('[data-map-src]'), function (slot) {
    var build = function () {
      if (slot.firstChild) return;
      var frame = document.createElement('iframe');
      frame.src = slot.dataset.mapSrc;
      frame.title = slot.dataset.mapTitle || 'Map';
      frame.loading = 'lazy';
      frame.referrerPolicy = 'no-referrer';
      slot.appendChild(frame);
    };
    if (!('IntersectionObserver' in window)) { build(); return; }
    var io = new IntersectionObserver(function (entries) {
      if (entries.some(function (e) { return e.isIntersecting; })) { io.disconnect(); build(); }
    }, { rootMargin: '200px' });
    io.observe(slot);
  });

  // Search. The index is generated from the pages and fetched the first time
  // the box is used, so it costs nothing to a reader who never searches.
  var searchInput = document.getElementById('search-input');
  if (searchInput) {
    var panel = document.getElementById('search-results');
    var list = document.getElementById('search-list');
    var group = document.getElementById('site-search');
    var openBtn = document.getElementById('search-open');
    var closeBtn = document.getElementById('search-close');
    var index = null, loading = null, active = -1, results = [];

    function load() {
      if (index) return Promise.resolve(index);
      if (!loading) {
        loading = fetch(searchInput.dataset.index)
          .then(function (r) { return r.ok ? r.json() : []; })
          .then(function (data) { index = data; return index; })
          .catch(function () { index = []; return index; });
      }
      return loading;
    }

    function escapeHtml(s) {
      return s.replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
      });
    }

    // Wrap each occurrence of a token in <mark>, on already-escaped text.
    function highlight(text, tokens) {
      var out = escapeHtml(text);
      tokens.forEach(function (tok) {
        var re = new RegExp('(' + tok.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
        out = out.replace(re, '<mark>$1</mark>');
      });
      return out;
    }

    function snippetFor(text, tokens) {
      var lower = text.toLowerCase(), at = -1;
      for (var i = 0; i < tokens.length && at < 0; i++) at = lower.indexOf(tokens[i]);
      if (at < 0) at = 0;
      var start = Math.max(0, at - 50);
      var cut = text.slice(start, start + 150);
      return (start > 0 ? '\u2026' : '') + cut + (start + 150 < text.length ? '\u2026' : '');
    }

    function rank(rec, tokens, q) {
      var title = rec.t.toLowerCase(), body = (rec.x || '').toLowerCase(), page = rec.p.toLowerCase();
      for (var i = 0; i < tokens.length; i++) {
        if (title.indexOf(tokens[i]) < 0 && body.indexOf(tokens[i]) < 0 && page.indexOf(tokens[i]) < 0) return -1;
      }
      var score = 0;
      if (title.indexOf(q) === 0) score += 100;
      else if (title.indexOf(q) >= 0) score += 60;
      tokens.forEach(function (t) { if (title.indexOf(t) >= 0) score += 10; });
      return score;
    }

    function render(q) {
      var tokens = q.toLowerCase().split(/\s+/).filter(Boolean);
      results = (index || []).map(function (rec) { return { rec: rec, score: rank(rec, tokens, q.toLowerCase()) }; })
        .filter(function (r) { return r.score >= 0; })
        .sort(function (a, b) { return b.score - a.score; })
        .slice(0, 8)
        .map(function (r) { return r.rec; });
      active = -1;
      list.innerHTML = '';
      if (!results.length) {
        list.innerHTML = '<li class="search-empty" role="presentation">No match for &ldquo;' + escapeHtml(q) + '&rdquo;</li>';
      } else {
        results.forEach(function (rec, i) {
          var li = document.createElement('li');
          li.className = 'pf-v6-c-menu__list-item';
          li.setAttribute('role', 'none');
          li.innerHTML = '<a class="pf-v6-c-menu__item" href="' + rec.u + '" role="option" id="search-opt-' + i + '">' +
            '<span class="pf-v6-c-menu__item-main"><span class="pf-v6-c-menu__item-text">' +
            highlight(rec.t, tokens) +
            '<span class="search-result-page">' + escapeHtml(rec.p) + '</span>' +
            '<span class="search-result-snippet">' + highlight(snippetFor(rec.x || '', tokens), tokens) + '</span>' +
            '</span></span></a>';
          list.appendChild(li);
        });
      }
      open(true);
    }

    function open(show) {
      panel.hidden = !show;
      searchInput.setAttribute('aria-expanded', show ? 'true' : 'false');
      if (!show) { active = -1; searchInput.removeAttribute('aria-activedescendant'); }
    }

    function setActive(i) {
      var opts = list.querySelectorAll('.pf-v6-c-menu__item');
      if (!opts.length) return;
      active = (i + opts.length) % opts.length;
      Array.prototype.forEach.call(opts, function (a, n) {
        a.classList.toggle('pf-m-focus', n === active);
        if (n === active) { a.scrollIntoView({ block: 'nearest' }); searchInput.setAttribute('aria-activedescendant', a.id); }
      });
    }

    function expand(show) {
      group.classList.toggle('pf-m-expanded', show);
      openBtn.setAttribute('aria-expanded', show ? 'true' : 'false');
      if (show) searchInput.focus();
      else { searchInput.value = ''; open(false); }
    }

    function run() {
      var q = searchInput.value.trim();
      if (q.length < 2) { open(false); return; }
      load().then(function () { if (searchInput.value.trim() === q) render(q); });
    }

    searchInput.addEventListener('input', run);
    searchInput.addEventListener('focus', function () { if (searchInput.value.trim().length >= 2) run(); });
    searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); if (panel.hidden) run(); else setActive(active + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(active - 1); }
      else if (e.key === 'Enter') {
        var opts = list.querySelectorAll('.pf-v6-c-menu__item');
        if (opts.length) { e.preventDefault(); (opts[active >= 0 ? active : 0]).click(); }
      } else if (e.key === 'Escape') { if (!panel.hidden) open(false); else { expand(false); openBtn.focus(); } }
    });
    openBtn.addEventListener('click', function () { expand(true); });
    closeBtn.addEventListener('click', function () { expand(false); openBtn.focus(); });
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.site-search') && !e.target.closest('.search-results')) {
        open(false);
        if (!searchInput.value.trim()) expand(false);
      }
    });
    list.addEventListener('click', function () { open(false); expand(false); });
  }

  // Accordions. The toggle owns the state: aria-expanded says it for assistive
  // technology, hidden takes the panel out for everyone, and PatternFly's
  // pf-m-expanded on the item turns the chevron. An anchor pointing into a
  // collapsed panel opens it first, so a link to #course-alpha still lands.
  var toggles = document.querySelectorAll('.pf-v6-c-accordion__toggle');
  if (toggles.length) {
    var setItem = function (toggle, open) {
      var panel = document.getElementById(toggle.getAttribute('aria-controls'));
      if (!panel) return;
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      panel.hidden = !open;
      var item = toggle.closest('.pf-v6-c-accordion__item');
      if (item) item.classList.toggle('pf-m-expanded', open);
    };

    Array.prototype.forEach.call(toggles, function (toggle) {
      toggle.addEventListener('click', function () {
        setItem(toggle, toggle.getAttribute('aria-expanded') !== 'true');
      });
    });

    var openFromHash = function () {
      var id = location.hash.slice(1);
      if (!id) return;
      var target = document.getElementById(id);
      if (!target) return;
      var panel = target.closest('.pf-v6-c-accordion__expandable-content');
      if (!panel) return;
      var toggle = document.getElementById(panel.getAttribute('aria-labelledby'));
      if (toggle) { setItem(toggle, true); target.scrollIntoView(); }
    };
    window.addEventListener('hashchange', openFromHash);
    openFromHash();
  }

  // About this page. PatternFly's about modal, opened from the footer. The
  // accessibility guidance for it asks for four things beyond showing the box:
  // focus moves into the dialog, Tab stays inside it, Escape closes it, and
  // whatever opened it gets focus back.
  var about = document.getElementById('about-page');
  var aboutOpen = document.getElementById('about-page-open');
  if (about && aboutOpen) {
    var aboutClose = document.getElementById('about-page-close');
    var opener = null;

    var focusable = function () {
      return Array.prototype.filter.call(
        about.querySelectorAll('a[href], button:not([disabled])'),
        function (el) { return el.offsetParent !== null; });
    };

    // Everything that is not the dialog is switched off while it is open, so a
    // screen reader cannot wander into the page behind it. inert does this for
    // pointer, keyboard and assistive technology at once; where it is missing,
    // aria-hidden still hides the background from a screen reader and the Tab
    // handler below keeps the keyboard inside.
    var siblings = Array.prototype.filter.call(document.body.children, function (el) {
      return el !== about && el.tagName !== 'SCRIPT';
    });
    var background = function (off) {
      siblings.forEach(function (el) {
        if ('inert' in HTMLElement.prototype) el.inert = off;
        if (off) el.setAttribute('aria-hidden', 'true');
        else el.removeAttribute('aria-hidden');
      });
    };

    var show = function () {
      opener = document.activeElement;
      about.hidden = false;
      background(true);
      var first = focusable()[0];
      if (first) first.focus();
    };

    var hide = function () {
      about.hidden = true;
      background(false);
      if (opener && opener.focus) opener.focus();
      opener = null;
    };

    aboutOpen.addEventListener('click', show);
    if (aboutClose) aboutClose.addEventListener('click', hide);

    // A click on the backdrop itself, not on the box sitting on top of it.
    about.addEventListener('click', function (e) {
      if (e.target === about) hide();
    });

    document.addEventListener('keydown', function (e) {
      if (about.hidden) return;
      if (e.key === 'Escape') { hide(); return; }
      if (e.key !== 'Tab') return;
      var items = focusable();
      if (!items.length) return;
      var first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
      }
    });
  }

  // Back to top.
  var totop = document.getElementById('back-to-top');
  if (totop) {
    var ticking = false;
    // Shown once the reader is well down a page that is long enough for the
    // trip back to be worth a button: two screens or more.
    function sync() {
      ticking = false;
      var sc = scroller();
      var longEnough = sc.scrollHeight > sc.clientHeight * 2;
      totop.classList.toggle('pf-m-hidden', !longEnough || sc.scrollTop < 600);
    }
    onScroll(function () {
      if (!ticking) { ticking = true; window.requestAnimationFrame(sync); }
    });
    sync();
    totop.querySelector('a').addEventListener('click', function (e) {
      e.preventDefault();
      var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      scroller().scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    });
  }
})();
