#!/usr/bin/env python3
# Copyright (C) 2026 Jiaxing Hu <gahing@gahingwoo.com>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License version 2 as published by the
# Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, see <https://www.gnu.org/licenses/>.
"""Render the site from content/ into page directories at the repo root.

Each page is a fragment in content/<slug>.html holding a gallery of cards; this
wraps it in the shell every page shares — PatternFly's page, masthead, sidebar
and the "on this page" rail — and writes <slug>/index.html. The rail is built
from the cards themselves, so a card added to a fragment appears in it without
anything else being edited.

    python3 tools/build.py

Writes the pages, the redirect stubs for the old Wix URLs, sitemap.xml and
robots.txt. Takes no arguments, and needs nothing installed.

The shell is PatternFly's own: masthead, sidebar, page main section. It follows
gahingwoo.com, which runs the same one.
"""

import hashlib
import html
import json
import pathlib
import re
import sys
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

# Where this build will actually be served from. GitHub writes CNAME when the
# custom domain is set in the repository's Pages settings, so it is the one
# place that already knows: while the rewrite sits on new.mabc.org.nz the
# canonical, og: and sitemap URLs point there, and they follow by themselves
# the day it moves to www. A build with no CNAME assumes the real address.
LIVE_DOMAIN = "www.mabc.org.nz"
_cname = ROOT / "CNAME"
DOMAIN = (_cname.read_text(encoding="utf-8").strip()
          if _cname.is_file() else LIVE_DOMAIN)
SITE = "https://" + DOMAIN
# Anywhere but the real address is a preview: it holds content the church has
# not signed off yet, so it asks not to be indexed and would otherwise compete
# with the live site for the same words.
IS_PREVIEW = DOMAIN != LIVE_DOMAIN
NAME = "Mt Albert Baptist"
ADDRESS = "732 New North Road, Mt Albert, Auckland"
PHONE = "09 849 2849"
EMAIL = "office@mabc.org.nz"
# The GPL asks that whoever receives the site can get at what built it, so the
# footer links here. Point it at the repository once it has one.
SOURCE = "https://github.com/gahingwoo/mabc-ws"
AUTHOR = "Ga Hing Woo (Jiaxing Hu)"
AUTHOR_URL = "https://github.com/gahingwoo"

# slug, directory, page title, subtitle shown beside it, meta description
PAGES = [
    ("index", "", "Mt Albert Baptist",
     "A church in Mt Albert since 1915",
     "A Baptist church in Mt Albert, Auckland since 1915. Services Sundays at "
     "9am and 11am, 732 New North Road. Everyone and anyone is welcome."),
    ("visit", "visit", "Plan a visit", "Sundays at 9am and 11am",
     "What a Sunday morning at Mt Albert Baptist is like: service times, where "
     "to take your children, live translation, and how to watch online."),
    ("next-gen", "next-gen", "Kids and youth", "From under 3 to Year 13 and beyond",
     "Children's ministry, Gravity for intermediate students, Traction youth "
     "group and Young Adults at Mt Albert Baptist."),
    ("get-involved", "get-involved", "Get involved", "Life groups, courses and missions",
     "Life Groups, Alpha and the other courses, global missions, the "
     "Newcomers' Lunch and 60+ Morning Tea at Mt Albert Baptist."),
    ("community", "community", "Community", "What we run for the neighbourhood",
     "The Mt Albert Community Pop Up, the Toy Library, English classes and the "
     "Glow Party — what Mt Albert Baptist runs for the neighbourhood."),
    ("about", "about", "About", "Our story, our team and how to reach us",
     "How Mt Albert Baptist began in 1915, what we stand for, our pastoral "
     "team, and how to get in touch."),
    ("give", "give", "Give", "How this church is funded",
     "Ways to give to Mt Albert Baptist: EFTPOS at the cafe, the Giving Post "
     "Box, and bank transfer for general, missions and building giving."),
]

# Sidebar navigation. Section title, then (label, href) per item.
NAV = [
    ("Church", [
        ("Home", "/"),
        ("Plan a visit", "/visit/"),
        ("Kids and youth", "/next-gen/"),
    ]),
    ("Get involved", [
        ("Life groups and courses", "/get-involved/"),
        ("Community", "/community/"),
        ("Give", "/give/"),
    ]),
    ("About", [
        ("About and contact", "/about/"),
    ]),
    ("Elsewhere", [
        ("Watch a service", "https://www.youtube.com/channel/UCw-WtY0mh2VpZUVWl0zdJ8w"),
        ("Live translation", "https://ezyspeech.mabc.qzz.io/"),
        ("English classes (ESOL)", "https://mabcESOL.org.nz"),
        ("Facebook", "https://facebook.com/MtAlbertBaptist"),
    ]),
]

REDIRECTS = {
    "sundays": "/visit/", "our": "/get-involved/", "connect": "/get-involved/",
    "courses": "/get-involved/", "alpha": "/get-involved/#courses",
    "cap-money-course": "/get-involved/#courses",
    "the-grace-course": "/get-involved/#courses",
    "freedom-in-christ": "/get-involved/#courses",
    "laidlaw-at-large": "/get-involved/#courses",
    "local-community": "/community/", "english-classes-esol": "/community/#esol",
    "mt-albert-community-pop-up": "/community/#pop-up",
    "mt-albert-toy-library": "/community/#toy-library",
    "copy-of-mt-albert-toy-library": "/get-involved/#newcomers",
    "copy-of-mt-albert-toy-library-1": "/community/#glow-party",
    "opening-week": "/about/", "copy-of-opening-week": "/about/",
    "our-team": "/about/#team", "contact": "/about/#contact",
    "sermons": "/visit/#sermons",
}

JSONLD = """{
  "@context": "https://schema.org",
  "@type": "Church",
  "name": "Mt Albert Baptist Church",
  "url": "%(site)s/",
  "telephone": "+64 9 849 2849",
  "email": "mailto:%(email)s",
  "foundingDate": "1915-09",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "732 New North Road",
    "addressLocality": "Mount Albert",
    "addressRegion": "Auckland",
    "addressCountry": "NZ"
  },
  "sameAs": ["https://facebook.com/MtAlbertBaptist"],
  "openingHoursSpecification": [
    { "@type": "OpeningHoursSpecification", "dayOfWeek": "Sunday", "opens": "09:00", "closes": "12:30" },
    { "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Tuesday", "Wednesday", "Thursday", "Friday"],
      "opens": "09:00", "closes": "14:30" }
  ]
}""" % {"site": SITE, "email": EMAIL}

CARET = ('<svg class="pf-v6-svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" '
         'role="img" width="1em" height="1em"><path d="M18.71 5.29a.996.996 0 0 0-1.41 0l-7.29 '
         '7.29-7.3-7.29a.987.987 0 0 0-1.41-.02.987.987 0 0 0-.02 1.41l.02.02 7.65 7.65c.29.29.68.44 '
         '1.06.44s.77-.15 1.06-.44l7.65-7.65a.996.996 0 0 0 0-1.41Z"/></svg>')


def cards(fragment):
    """The cards on this page, for the rail: every card that carries an id."""
    return re.findall(
        r'<div class="pf-v6-c-card"[^>]*\bid="([^"]+)"[^>]*data-rail="([^"]+)"', fragment)


def search_records(slug, href, heading, fragment):
    """One record per card, built from the page itself: a card is findable
    because it is there, not because someone remembered to index it. Slices
    run from one card to the next rather than matching a closing tag, which
    nesting makes unreliable."""
    def text_of(chunk):
        chunk = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", chunk)
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", chunk))).strip()

    starts = [(m.start(), m.group(1), text_of(m.group(2))) for m in re.finditer(
        r'<div class="pf-v6-c-card"[^>]*\bid="([^"]+)"[^>]*>\s*'
        r'(?:<div class="pf-v6-c-card__header[^>]*>.*?</div>\s*)?'
        r'<div class="pf-v6-c-card__title"><h2 class="pf-v6-c-card__title-text">(.*?)</h2>',
        fragment, re.S)]
    out = []
    for i, (pos, cid, title) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(fragment)
        out.append({"t": title, "u": href + "#" + cid, "p": heading,
                    "x": text_of(fragment[pos:end])})
    return out


def render_sermons():
    """The last few Sunday services, read from assets/sermons.json, which
    tools/fetch_sermons.py refreshes from the church's YouTube feed. Returns
    "" when the file is missing or empty, and the page falls back to the plain
    link it had before: nothing here is allowed to break a build."""
    path = ROOT / "assets/sermons.json"
    if not path.is_file():
        return ""
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return ""
    rows = []
    for it in items[:6]:
        try:
            when = date.fromisoformat(it["d"])
        except (KeyError, ValueError):
            continue
        # "Sunday 6 September" reads as a date to a person; the year is only
        # spelled out once it is not the current one.
        label = when.strftime("%A %-d %B")
        if when.year != date.today().year:
            label += when.strftime(" %Y")
        topic = html.escape(it.get("s") or "")
        rows.append(
            '        <div class="pf-v6-c-description-list__group">'
            '<dt class="pf-v6-c-description-list__term">'
            '<span class="pf-v6-c-description-list__text">%s</span></dt>'
            '<dd class="pf-v6-c-description-list__description">'
            '<div class="pf-v6-c-description-list__text">'
            '<a href="https://www.youtube.com/watch?v=%s" data-video="%s" '
            'data-video-title="%s">%s</a>'
            '<span class="meta">%s</span></div></dd></div>'
            % (label, html.escape(it.get("v", "")), html.escape(it.get("v", "")),
               html.escape("%s, %s" % (label, it.get("t", ""))),
               topic or "Watch the service", html.escape(it.get("t", ""))))
    if not rows:
        return ""
    return ('<div class="pf-v6-u-mt-lg"><dl class="pf-v6-c-description-list '
            'pf-m-horizontal-on-sm kv">\n' + "\n".join(rows) + "\n</dl></div>")


def render_last_service():
    """One line for the home page: what was on last Sunday. Both services of a
    Sunday share a topic, so they are named together rather than listed twice."""
    path = ROOT / "assets/sermons.json"
    if not path.is_file():
        return ""
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return ""
    if not items:
        return ""
    newest = items[0]["d"]
    same = [i for i in items if i["d"] == newest]
    try:
        when = date.fromisoformat(newest)
    except ValueError:
        return ""
    times = " and ".join(dict.fromkeys(i["t"] for i in reversed(same)))
    topic = next((i.get("s") for i in same if i.get("s")), "")
    label = when.strftime("%-d %B")
    if when.year != date.today().year:
        label += when.strftime(" %Y")
    return ('    <div class="pf-v6-c-description-list__group">'
            '<dt class="pf-v6-c-description-list__term">'
            '<span class="pf-v6-c-description-list__text">Last Sunday</span></dt>'
            '<dd class="pf-v6-c-description-list__description">'
            '<div class="pf-v6-c-description-list__text">'
            '<a href="https://www.youtube.com/watch?v=%s" data-video="%s" '
            'data-video-title="Last Sunday">%s</a>'
            '<span class="meta">%s, %s</span></div></dd></div>\n'
            % (html.escape(same[0].get("v", "")), html.escape(same[0].get("v", "")),
               html.escape(topic) if topic else "Watch the service",
               html.escape(label), html.escape(times)))


def render_nav(current):
    out = []
    for title, items in NAV:
        tid = re.sub(r"[^a-z]+", "-", title.lower()).strip("-") + "-title"
        out.append('        <section class="pf-v6-c-nav__section" aria-labelledby="%s">\n'
                   '          <h2 class="pf-v6-c-nav__section-title" id="%s">%s</h2>\n'
                   '          <ul class="pf-v6-c-nav__list" role="list">' % (tid, tid, html.escape(title)))
        for label, href in items:
            cur = href == current
            out.append('            <li class="pf-v6-c-nav__item">'
                       '<a href="%s" class="pf-v6-c-nav__link%s"%s>'
                       '<span class="pf-v6-c-nav__link-text">%s</span></a></li>'
                       % (href, " pf-m-current" if cur else "",
                          ' aria-current="page"' if cur else "", html.escape(label)))
        out.append("          </ul>\n        </section>")
    return "\n".join(out)


def render_rail(sections):
    if not sections:
        return ""
    items = "\n".join(
        '                <li class="pf-v6-c-jump-links__item">'
        '<span class="pf-v6-c-jump-links__link">'
        '<a class="pf-v6-c-button pf-m-link" href="#%s"><span class="pf-v6-c-button__text">'
        '<span class="pf-v6-c-jump-links__link-text">%s</span></span></a></span></li>'
        % (sid, html.escape(label)) for sid, label in sections)
    return """          <aside class="page-rail no-print">
            <nav class="pf-v6-c-jump-links pf-m-vertical pf-m-expandable pf-m-non-expandable-on-xl" aria-label="On this page" id="jump-nav" data-scrollable=".pf-v6-c-page__main">
              <div class="pf-v6-c-jump-links__header" id="jump-header">
                <div class="pf-v6-c-jump-links__toggle">
                  <button class="pf-v6-c-button pf-m-plain" type="button" aria-expanded="false" aria-controls="jump-list" id="jump-toggle">
                    <span class="pf-v6-c-button__icon pf-m-start"><span class="pf-v6-c-jump-links__toggle-icon">%s</span></span>
                    <span class="pf-v6-c-button__text">On this page</span>
                  </button>
                </div>
                <div class="pf-v6-c-jump-links__label">On this page</div>
              </div>
              <ul class="pf-v6-c-jump-links__list" role="list" aria-labelledby="jump-header" id="jump-list">
%s
              </ul>
            </nav>
          </aside>
""" % (CARET, items)


SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(description)s">
<link rel="canonical" href="%(canonical)s">
%(noindex)s
<link rel="icon" href="/assets/brand/mark.png" type="image/png" sizes="208x208">
<link rel="apple-touch-icon" href="/assets/brand/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="%(name)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(description)s">
<meta property="og:url" content="%(canonical)s">
<meta property="og:image" content="%(site)s/assets/img/building.jpg">
<meta property="og:image:width" content="1600">
<meta property="og:image:height" content="900">
<meta name="twitter:card" content="summary_large_image">
<script>
  (function () {
    var saved = null;
    try { saved = localStorage.getItem('theme'); } catch (e) {}
    if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.classList.add('pf-v6-theme-dark');
    }
  })();
</script>
%(jsonld)s<link rel="stylesheet" href="%(pf_css)s">
<link rel="stylesheet" href="%(site_css)s">
</head>
<body>
<div class="pf-v6-c-page">
  <div class="pf-v6-c-skip-to-content">
    <a class="pf-v6-c-button pf-m-primary" href="#main-content"><span class="pf-v6-c-button__text">Skip to content</span></a>
  </div>
  <header class="pf-v6-c-masthead pf-m-display-inline">
    <div class="pf-v6-c-masthead__main">
      <span class="pf-v6-c-masthead__toggle">
        <button class="pf-v6-c-button pf-m-hamburger pf-m-plain" type="button" aria-label="Site navigation" aria-expanded="false" aria-controls="site-sidebar" id="nav-toggle">
          <span class="pf-v6-c-button__icon"><svg viewBox="0 0 10 10" class="pf-v6-c-button--hamburger-icon pf-v6-svg" width="1em" height="1em"><path class="pf-v6-c-button--hamburger-icon--top" d="M1,1 L9,1"/><path class="pf-v6-c-button--hamburger-icon--middle" d="M1,5 L9,5"/><path class="pf-v6-c-button--hamburger-icon--arrow" d="M1,5 L1,5 L1,5"/><path class="pf-v6-c-button--hamburger-icon--bottom" d="M9,9 L1,9"/></svg></span>
        </button>
      </span>
      <div class="pf-v6-c-masthead__brand">
        <a class="pf-v6-c-masthead__logo brand" href="/">
          <img class="pf-v6-c-brand brand-mark" src="/assets/brand/mark.png" width="208" height="208" alt="">
          <span class="brand-name">%(name)s</span>
        </a>
      </div>
    </div>
    <div class="pf-v6-c-masthead__content">
      <div class="search-slot">
        <div class="pf-v6-c-input-group pf-m-search-expandable pf-m-plain site-search" id="site-search">
          <div class="pf-v6-c-input-group__item pf-m-search-input">
            <div class="pf-v6-c-text-input-group">
              <div class="pf-v6-c-text-input-group__main pf-m-icon">
                <span class="pf-v6-c-text-input-group__text">
                  <span class="pf-v6-c-text-input-group__icon"><svg class="pf-v6-svg" fill="currentColor" viewBox="0 0 512 512" aria-hidden="true" role="img" width="1em" height="1em"><path d="M505 442.7L405.3 343c-4.5-4.5-10.6-7-17-7H372c27.6-35.3 44-79.7 44-128C416 93.1 322.9 0 208 0S0 93.1 0 208s93.1 208 208 208c48.3 0 92.7-16.4 128-44v16.3c0 6.4 2.5 12.5 7 17l99.7 99.7c9.4 9.4 24.6 9.4 33.9 0l28.3-28.3c9.4-9.4 9.4-24.6.1-34zM208 336c-70.7 0-128-57.2-128-128 0-70.7 57.2-128 128-128 70.7 0 128 57.2 128 128 0 70.7-57.2 128-128 128z"/></svg></span>
                  <input class="pf-v6-c-text-input-group__text-input" type="text" id="search-input"
                         placeholder="Search this site" autocomplete="off" spellcheck="false"
                         aria-label="Search this site" role="combobox" aria-expanded="false"
                         aria-controls="search-results" aria-autocomplete="list"
                         data-index="/assets/search-index.json">
                </span>
              </div>
            </div>
          </div>
          <div class="pf-v6-c-input-group__item pf-m-search-expand pf-m-plain">
            <button class="pf-v6-c-button pf-m-plain" type="button" id="search-open"
                    aria-label="Search this site" aria-expanded="false">
              <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg" fill="currentColor" viewBox="0 0 512 512" aria-hidden="true" role="img" width="1em" height="1em"><path d="M505 442.7L405.3 343c-4.5-4.5-10.6-7-17-7H372c27.6-35.3 44-79.7 44-128C416 93.1 322.9 0 208 0S0 93.1 0 208s93.1 208 208 208c48.3 0 92.7-16.4 128-44v16.3c0 6.4 2.5 12.5 7 17l99.7 99.7c9.4 9.4 24.6 9.4 33.9 0l28.3-28.3c9.4-9.4 9.4-24.6.1-34zM208 336c-70.7 0-128-57.2-128-128 0-70.7 57.2-128 128-128 70.7 0 128 57.2 128 128 0 70.7-57.2 128-128 128z"/></svg></span>
            </button>
          </div>
          <div class="pf-v6-c-input-group__item pf-m-search-action pf-m-plain">
            <button class="pf-v6-c-button pf-m-plain" type="button" id="search-close" aria-label="Close search">
              <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg" viewBox="0 0 352 512" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M242.72 256l100.07-100.07c12.28-12.28 12.28-32.19 0-44.48l-22.24-22.24c-12.28-12.28-32.19-12.28-44.48 0L176 189.28 75.93 89.21c-12.28-12.28-32.19-12.28-44.48 0L9.21 111.45c-12.28 12.28-12.28 32.19 0 44.48L109.28 256 9.21 356.07c-12.28 12.28-12.28 32.19 0 44.48l22.24 22.24c12.28 12.28 32.2 12.28 44.48 0L176 322.72l100.07 100.07c12.28 12.28 32.2 12.28 44.48 0l22.24-22.24c12.28-12.28 12.28-32.19 0-44.48L242.72 256z"/></svg></span>
            </button>
          </div>
        </div>
        <div class="pf-v6-c-menu search-results" id="search-results" hidden>
          <div class="pf-v6-c-menu__content">
            <ul class="pf-v6-c-menu__list" role="listbox" aria-label="Search results" id="search-list"></ul>
          </div>
        </div>
      </div>
      <button class="pf-v6-c-button pf-m-plain theme-toggle" id="theme-toggle" type="button" aria-label="Toggle light and dark theme">
        <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg icon-moon" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M10.6 2a8 8 0 1 0 7.4 11 6.6 6.6 0 0 1-7.4-11Z"/></svg><svg class="pf-v6-svg icon-sun" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true" role="img" width="1em" height="1em"><circle cx="10" cy="10" r="3.6"/><path d="M10 1.5v2.2M10 16.3v2.2M1.5 10h2.2M16.3 10h2.2M4 4l1.6 1.6M14.4 14.4 16 16M4 16l1.6-1.6M14.4 5.6 16 4"/></svg></span>
      </button>
      <a class="pf-v6-c-button pf-m-primary masthead-give" href="/give/"><span class="pf-v6-c-button__text">Give</span></a>
    </div>
  </header>
  <div class="pf-v6-c-backdrop site-backdrop" id="site-backdrop" hidden></div>
  <aside class="pf-v6-c-page__sidebar" id="site-sidebar">
    <div class="pf-v6-c-page__sidebar-main">
      <div class="pf-v6-c-page__sidebar-body pf-m-page-insets">
        <nav class="pf-v6-c-nav" aria-label="Site">
%(nav)s
        </nav>
      </div>
    </div>
  </aside>
  <div class="pf-v6-c-page__main-container" tabindex="-1">
    <main class="pf-v6-c-page__main doc-page%(railcls)s" tabindex="-1" id="main-content">
      <section class="pf-v6-c-page__main-section pf-m-limit-width" aria-label="%(heading)s">
        <div class="pf-v6-c-page__main-body">
%(rail)s          <div class="page-content">
%(head)s%(content)s

          </div>
        </div>
      </section>

      <footer class="pf-v6-c-page__main-section site-footer">
        <div class="pf-v6-c-page__main-body">
          <div class="pf-v6-l-grid pf-m-gutter">
            <div class="pf-v6-l-grid__item pf-m-6-col-on-sm pf-m-3-col-on-lg">
              <p class="foot-title">Visit</p>
              <nav aria-label="Visit">
                <a href="/visit/">Plan a visit</a>
                <a href="/visit/#services">Service times</a>
                <a href="/visit/#translation">Live translation</a>
                <a href="/visit/#sermons">Sermons</a>
              </nav>
            </div>
            <div class="pf-v6-l-grid__item pf-m-6-col-on-sm pf-m-3-col-on-lg">
              <p class="foot-title">Get involved</p>
              <nav aria-label="Get involved">
                <a href="/next-gen/">Kids and youth</a>
                <a href="/get-involved/">Life groups and courses</a>
                <a href="/community/">Community</a>
                <a href="/give/">Give</a>
              </nav>
            </div>
            <div class="pf-v6-l-grid__item pf-m-6-col-on-sm pf-m-3-col-on-lg">
              <p class="foot-title">Elsewhere</p>
              <nav aria-label="Elsewhere">
                <a href="https://www.youtube.com/channel/UCw-WtY0mh2VpZUVWl0zdJ8w">Watch a service</a>
                <a href="https://ezyspeech.mabc.qzz.io/">Live translation</a>
                <a href="https://mabcESOL.org.nz">English classes</a>
                <a href="https://facebook.com/MtAlbertBaptist">Facebook</a>
              </nav>
            </div>
            <div class="pf-v6-l-grid__item pf-m-12-col-on-sm pf-m-3-col-on-lg">
              <span class="brand foot-brand">
                <img class="pf-v6-c-brand brand-mark" src="/assets/brand/mark.png" width="208" height="208" alt="" loading="lazy">
                <span class="brand-name">%(name)s</span>
              </span>
              <p class="foot-about">A church in Mt Albert since 1915 &mdash; a place to connect,
                grow, serve and give. Everyone and anyone is welcome.</p>
              <address>
                %(address)s<br>
                <a href="tel:+6498492849">%(phone)s</a><br>
                <a href="mailto:%(email)s">%(email)s</a><br>
                Church office Tuesday&ndash;Friday, 9am&ndash;2.30pm
              </address>
            </div>
          </div>
        </div>
      </footer>

      <section class="pf-v6-c-page__main-section pf-m-no-fill foot-legal">
        <div class="pf-v6-c-page__main-body">
          <span>Copyright &copy; 1915&ndash;<span id="year">%(year)s</span> %(name)s Church</span>
          <span>Website made by <a href="%(author_url)s">%(author)s</a></span>
          <span><a href="%(source)s">View page source</a></span>
          <span><button class="link-button" type="button" id="about-page-open">About this site</button></span>
          <span><a href="/about/#contact">Contact</a></span>
        </div>
      </section>
    </main>
  </div>
</div>
<div class="pf-v6-c-backdrop about-backdrop" id="about-page" hidden>
  <div class="pf-v6-l-bullseye">
  <div class="pf-v6-c-about-modal-box" role="dialog" aria-modal="true" aria-labelledby="about-page-title">
    <div class="pf-v6-c-about-modal-box__brand">
      <img class="pf-v6-c-about-modal-box__brand-image" src="/assets/brand/mark.png" width="208" height="208" alt="">
    </div>
    <div class="pf-v6-c-about-modal-box__close">
      <button class="pf-v6-c-button pf-m-plain" type="button" id="about-page-close" data-dialog-close aria-label="Close About this site">
        <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg" viewBox="0 0 352 512" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M242.72 256l100.07-100.07c12.28-12.28 12.28-32.19 0-44.48l-22.24-22.24c-12.28-12.28-32.19-12.28-44.48 0L176 189.28 75.93 89.21c-12.28-12.28-32.19-12.28-44.48 0L9.21 111.45c-12.28 12.28-12.28 32.19 0 44.48L109.28 256 9.21 356.07c-12.28 12.28-12.28 32.19 0 44.48l22.24 22.24c12.28 12.28 32.2 12.28 44.48 0L176 322.72l100.07 100.07c12.28 12.28 32.2 12.28 44.48 0l22.24-22.24c12.28-12.28 12.28-32.19 0-44.48L242.72 256z"/></svg></span>
      </button>
    </div>
    <div class="pf-v6-c-about-modal-box__header">
      <h1 class="pf-v6-c-title pf-m-4xl" id="about-page-title">About this site</h1>
    </div>
    <div class="pf-v6-c-about-modal-box__content">
      <dl class="pf-v6-c-description-list pf-m-horizontal">
%(aboutrows)s
      </dl>
      <p class="pf-v6-c-about-modal-box__strapline">
        Copyright &copy; 1915&ndash;%(year)s %(name)s Church. The code behind this site is
        free software under the GNU General Public License, version 2.
      </p>
    </div>
  </div>
  </div>
</div>
<div class="pf-v6-c-backdrop sermon-backdrop" id="sermon-player" hidden>
  <div class="pf-v6-l-bullseye">
  <div class="pf-v6-c-modal-box pf-m-lg" role="dialog" aria-modal="true" aria-labelledby="sermon-player-title">
    <div class="pf-v6-c-modal-box__close">
      <button class="pf-v6-c-button pf-m-plain" type="button" data-dialog-close aria-label="Close the player">
        <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg" viewBox="0 0 352 512" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M242.72 256l100.07-100.07c12.28-12.28 12.28-32.19 0-44.48l-22.24-22.24c-12.28-12.28-32.19-12.28-44.48 0L176 189.28 75.93 89.21c-12.28-12.28-32.19-12.28-44.48 0L9.21 111.45c-12.28 12.28-12.28 32.19 0 44.48L109.28 256 9.21 356.07c-12.28 12.28-12.28 32.19 0 44.48l22.24 22.24c12.28 12.28 32.2 12.28 44.48 0L176 322.72l100.07 100.07c12.28 12.28 32.2 12.28 44.48 0l22.24-22.24c12.28-12.28 12.28-32.19 0-44.48L242.72 256z"/></svg></span>
      </button>
    </div>
    <header class="pf-v6-c-modal-box__header">
      <h1 class="pf-v6-c-modal-box__title" id="sermon-player-title">
        <span class="pf-v6-c-modal-box__title-text" data-player-title>Sermon</span>
      </h1>
    </header>
    <div class="pf-v6-c-modal-box__body">
      <div class="player-frame" data-player-slot></div>
    </div>
  </div>
  </div>
</div>
<div class="pf-v6-c-back-to-top pf-m-hidden" id="back-to-top">
  <a class="pf-v6-c-button pf-m-primary" href="#main-content">
    <span class="pf-v6-c-button__text">Back to top</span>
    <span class="pf-v6-c-button__icon pf-m-end"><svg class="pf-v6-svg" viewBox="0 0 448 512" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M6.101 359.293 25.9 379.092a12 12 0 0 0 16.971 0L224 198.393l181.13 180.698a12 12 0 0 0 16.971 0l19.799-19.799a12 12 0 0 0 0-16.971L232.485 132.908a12 12 0 0 0-16.971 0L6.101 342.322a12 12 0 0 0 0 16.971z"/></svg></span>
  </a>
</div>
<script src="%(site_js)s"></script>
</body>
</html>
"""

STUB = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Redirecting</title>
<link rel="canonical" href="%(site)s%(to)s">
<meta http-equiv="refresh" content="0;url=%(to)s">
<meta name="robots" content="noindex">
<link rel="icon" href="/assets/brand/mark.png" type="image/png" sizes="208x208">
<link rel="stylesheet" href="/assets/patternfly/patternfly-site.css">
<link rel="stylesheet" href="/assets/site.css">
</head>
<body>
<div class="pf-v6-l-bullseye redirect">
  <div>
    <svg class="pf-v6-c-spinner pf-m-xl" role="progressbar" viewBox="0 0 100 100" aria-label="Redirecting">
      <circle class="pf-v6-c-spinner__path" cx="50" cy="50" r="45" fill="none"></circle>
    </svg>
    <p class="pf-v6-c-content--p">Redirecting to <a href="%(to)s">%(to)s</a></p>
  </div>
</div>
</body>
</html>
"""


def about_rows(pf_version):
    """What the site is made of and what it does with a reader. Everything here
    is true of every page, and the two claims that matter most to a visitor,
    that nothing counts them and nothing but a theme choice is kept, are things
    the code either does or does not do."""
    def link(url, label):
        return '<a href="%s">%s</a>' % (html.escape(url), html.escape(label))

    # Values are finished HTML: plain strings are escaped here, the two that
    # lead somewhere are anchors.
    rows = [
        ("Built with", html.escape(pf_version)),
        ("Analytics", "None. Your visit is not counted."),
        ("Loaded from elsewhere",
         "The map on Plan a visit, and a sermon when you press play"),
        ("Kept on your device", "Your light or dark choice"),
        ("Licence", "GPL-2.0, code only"),
        ("Made by", link(AUTHOR_URL, AUTHOR)),
        ("Source", link(SOURCE, SOURCE.replace("https://", ""))),
    ]
    return "\n".join(
        '        <div class="pf-v6-c-description-list__group">'
        '<dt class="pf-v6-c-description-list__term">'
        '<span class="pf-v6-c-description-list__text">%s</span></dt>'
        '<dd class="pf-v6-c-description-list__description">'
        '<div class="pf-v6-c-description-list__text">%s</div></dd></div>'
        % (term, value) for term, value in rows)


def build():
    if not CONTENT.is_dir():
        sys.exit("no content/ directory next to %s" % ROOT)

    # A file edited in place is the one thing a browser will go on serving from
    # its cache for a week. Every /assets/ URL in a built page gets a hash of
    # that file's own contents appended, so a changed file is a different URL
    # and an unchanged one keeps being served from the cache. This runs over the
    # finished page rather than at each reference, so stylesheets, scripts,
    # photographs and the favicon are all covered without anyone remembering to.
    seen = {}

    def stamp(match):
        path = match.group(0).lstrip("/")
        if path not in seen:
            f = ROOT / path
            if not f.is_file():
                sys.exit("%s is referenced but does not exist" % match.group(0))
            seen[path] = hashlib.sha256(f.read_bytes()).hexdigest()[:8]
        return "%s?v=%s" % (match.group(0), seen[path])

    ASSET = re.compile(r"/assets/[A-Za-z0-9._/-]+\.[A-Za-z0-9]+")

    version_file = ROOT / "assets/patternfly/VERSION"
    # The VERSION file records the package name; the modal shows the product.
    pf_version = "PatternFly 6"
    if version_file.is_file():
        first = version_file.read_text(encoding="utf-8").splitlines()[0]
        pf_version = "PatternFly " + first.rsplit(" ", 1)[-1]

    aboutrows = about_rows(pf_version)
    sermons = render_sermons()
    last_service = render_last_service()

    assets = {
        "pf_css": "/assets/patternfly/patternfly-site.css",
        "site_css": "/assets/site.css",
        "site_js": "/assets/site.js",
        "aboutrows": aboutrows,
        "noindex": '<meta name="robots" content="noindex">\n' if IS_PREVIEW else "",
    }

    # The index is written before the pages, so the hash appended to its URL in
    # the masthead is the hash of the file the reader will actually fetch.
    records = []
    for slug, directory, heading, _subtitle, _description in PAGES:
        frag = CONTENT / (slug + ".html")
        if not frag.is_file():
            sys.exit("missing %s" % frag)
        records += search_records(slug, "/" + (directory + "/" if directory else ""),
                                  heading, frag.read_text(encoding="utf-8"))
    (ROOT / "assets/search-index.json").write_text(
        json.dumps(records, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    written = []
    for slug, directory, heading, subtitle, description in PAGES:
        frag = CONTENT / (slug + ".html")
        if not frag.is_file():
            sys.exit("missing %s" % frag)
        fragment = frag.read_text(encoding="utf-8").rstrip()
        # A fragment asks for the generated list by name, so the builder
        # does not need to know which card on which page it belongs in.
        fragment = fragment.replace("{{sermons}}", sermons)
        fragment = fragment.replace("{{last-service}}", last_service)
        rail = cards(fragment)

        href = "/" + (directory + "/" if directory else "")
        out = SHELL % dict(assets,
            title=html.escape(heading if slug == "index" else "%s | %s" % (heading, NAME)),
            description=html.escape(description),
            canonical=SITE + href, site=SITE, name=NAME, address=ADDRESS,
            heading=heading,
            phone=PHONE, email=EMAIL, year=date.today().year,
            author=AUTHOR, author_url=AUTHOR_URL, source=SOURCE,
            head="" if slug == "index" else (
                '            <div class="page-head">\n'
                '              <h1 class="page-title" id="page-title">%s <span class="subtitle">%s</span></h1>\n'
                '              <a class="pf-v6-c-button pf-m-secondary" href="/visit/">'
                '<span class="pf-v6-c-button__text">Plan a visit</span></a>\n'
                '            </div>\n' % (heading, subtitle)),
            nav=render_nav(href), rail=render_rail(rail),
            railcls=" with-rail" if rail else "",
            content=fragment,
            jsonld=('<script type="application/ld+json">\n%s\n</script>\n' % JSONLD)
                   if slug == "index" else "")

        target = ROOT / directory / "index.html" if directory else ROOT / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(ASSET.sub(stamp, out), encoding="utf-8")
        written.append((href, target.relative_to(ROOT)))

    for old, to in REDIRECTS.items():
        target = ROOT / old / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(ASSET.sub(stamp, STUB % {"site": SITE, "to": to}), encoding="utf-8")

    today = date.today().isoformat()
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join("  <url><loc>%s%s</loc><lastmod>%s</lastmod></url>"
                    % (SITE, href, today) for href, _ in written)
        + "\n</urlset>\n", encoding="utf-8")
    # Crawlers are welcome everywhere, preview included: the pages should be
    # readable by anything that comes looking. Keeping them out of search
    # results while the content is unconfirmed is the noindex tag's job, and
    # that only works if the crawler is allowed in to read it.
    (ROOT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE,
        encoding="utf-8")

    for href, path in written:
        print("%-16s %s" % (href, path))
    print("%d redirect stubs, sitemap.xml, robots.txt" % len(REDIRECTS))


if __name__ == "__main__":
    build()
