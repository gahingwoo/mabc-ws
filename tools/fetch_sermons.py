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
"""Refresh assets/sermons.json from the church's YouTube feed.

The site is static, so what it says about the church is only as current as the
last build. The one thing that moves every week is the Sunday livestream, and
YouTube publishes a channel feed that needs no key, so the recent services can
be read off it at build time instead of being typed in by hand.

    python3 tools/fetch_sermons.py

Writes assets/sermons.json. On any network or parsing failure it leaves the
existing file alone and exits 0: a site that builds with last week's list is
better than one that does not build.

Two things are deliberately excluded. Funerals are livestreamed on this channel
too, and a family's funeral does not belong in a list of recent sermons; they
are dropped by time of day and again by name. And a service that has not
happened yet is dropped, because YouTube holds a stream open days in advance
and a plan is not a fact.
"""
import datetime
import json
import pathlib
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets/sermons.json"
CHANNEL = "UCw-WtY0mh2VpZUVWl0zdJ8w"
FEED = "https://www.youtube.com/feeds/videos.xml?channel_id=" + CHANNEL
KEEP = 6

NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]


def service_time(title):
    """The 9am or 11am a Sunday service carries in its title, or None."""
    m = re.search(r"\b(9|11)\s*(?:\.\d+)?\s*am\b", title, re.I)
    return m.group(1) + "am" if m else None


def service_date(title, published):
    """The date the service was held. The title carries it and the upload date
    does not always: a stream opened on Friday for Sunday is published on the
    Friday. Falls back to the upload date when the title has none."""
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)(?:\s+(\d{4}))?", title)
    if m and m.group(2).lower() in MONTHS:
        day, month = int(m.group(1)), MONTHS.index(m.group(2).lower()) + 1
        year = int(m.group(3)) if m.group(3) else published.year
        try:
            return datetime.date(year, month, day)
        except ValueError:
            pass
    return published


def topic(title):
    """What is left of the title once the boilerplate is gone: the series or
    the speaker, which is the only part worth showing beside a date."""
    t = re.sub(r"^\s*MABC\s+Live\s+Stream\s*", "", title, flags=re.I)
    t = re.sub(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:%s)\b" % "|".join(MONTHS), " ", t, flags=re.I)
    t = re.sub(r"\b(?:%s)\s+\d{1,2}(?:st|nd|rd|th)?\b" % "|".join(MONTHS), " ", t, flags=re.I)
    t = re.sub(r"\b\d{1,2}\s*(?:\.\d+)?\s*am\b", " ", t, flags=re.I)
    t = re.sub(r"\b(?:19|20)\d{2}\b", " ", t)
    # Only the first "Service" is boilerplate. A second one is part of what
    # the service was: "Youth Service" must not come out as "Youth".
    t = re.sub(r"\bservice\b", " ", t, flags=re.I, count=1)
    t = re.sub(r"[()]", " ", t)
    return re.sub(r"\s+", " ", t).strip(" -–—,.")


def fetch():
    with urllib.request.urlopen(FEED, timeout=30) as r:
        return ET.fromstring(r.read())


def main():
    try:
        root = fetch()
    except Exception as e:                      # network, DNS, XML, anything
        print("could not refresh: %s" % e)
        print("keeping %s as it is" % OUT.relative_to(ROOT))
        return 0

    today = datetime.date.today()
    out = []
    for entry in root.findall("a:entry", NS):
        title = (entry.findtext("a:title", "", NS) or "").strip()
        vid = entry.findtext("yt:videoId", "", NS)
        published = entry.findtext("a:published", "", NS)[:10]
        if not (title and vid and published):
            continue
        # A funeral is livestreamed on this channel too. It is not a sermon and
        # it is not ours to advertise: dropped here by name, and by the time of
        # day above, so neither check is load-bearing on its own.
        if "funeral" in title.lower():
            continue
        when = service_time(title)
        if not when:
            continue
        held = service_date(title, datetime.date(*map(int, published.split("-"))))
        if held > today:                        # a stream opened in advance
            continue
        out.append({"d": held.isoformat(), "t": when, "s": topic(title), "v": vid})

    if not out:
        print("feed had no past Sunday services; keeping the existing file")
        return 0

    # "11am" sorts before "9am" as a string, so the hour is compared as a
    # number and the later service of a Sunday comes first.
    out.sort(key=lambda r: (r["d"], int(r["t"][:-2])), reverse=True)
    out = out[:KEEP]
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
    print("%d services, newest %s" % (len(out), out[0]["d"]))
    for r in out:
        print("  %s  %-4s %s" % (r["d"], r["t"], r["s"] or "—"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
