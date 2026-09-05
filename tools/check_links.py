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
"""Check every link in the built pages.

Internal links must resolve to a file that exists, and a #fragment must match
an id on the page it points at. External links are listed rather than fetched,
so the check stays offline and fast; pass --external to request each one.

    python3 tools/check_links.py
    python3 tools/check_links.py --external

Exits non-zero if anything is broken, so it can gate a deploy.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# The site's own canonical URLs point at a domain that is not serving this site
# yet, so they are not "external" for the purpose of this check.
SITE = "https://www.mabc.org.nz"
ATTR = re.compile(r'\b(?:href|src)="([^"]+)"')
ID = re.compile(r'\bid="([^"]+)"')


def pages():
    for p in sorted(ROOT.glob("*/index.html")) + [ROOT / "index.html"]:
        if "assets" not in p.parts and "content" not in p.parts:
            yield p


def resolve(target):
    """A site-absolute path to the file that serves it, or None."""
    p = ROOT / target.lstrip("/")
    if p.is_dir():
        p = p / "index.html"
    return p if p.is_file() else None


def main():
    ids = {}
    for p in pages():
        ids[p] = set(ID.findall(p.read_text(encoding="utf-8")))

    broken, external = [], set()
    for p in pages():
        here = p.relative_to(ROOT)
        for link in ATTR.findall(p.read_text(encoding="utf-8")):
            if link.startswith(SITE):
                continue
            if link.startswith(("http://", "https://")):
                external.add(link)
                continue
            if link.startswith(("mailto:", "tel:", "data:")):
                continue
            path, _, frag = link.partition("#")
            # Assets carry a ?v= content hash for cache busting; the file on
            # disk is the part before it.
            path = path.partition("?")[0]
            target = p
            if path:
                if not path.startswith("/"):
                    broken.append((here, link, "relative link — use a site-absolute path"))
                    continue
                found = resolve(path)
                if found is None:
                    broken.append((here, link, "no such file"))
                    continue
                target = found
            if frag and target in ids and frag not in ids[target]:
                broken.append((here, link, "no id %r on that page" % frag))

    for where, link, why in broken:
        print("BROKEN  %-22s %-44s %s" % (where, link, why))

    if "--external" in sys.argv:
        import subprocess
        print()
        for url in sorted(external):
            # curl rather than urllib: it follows redirects, speaks the TLS
            # these hosts want, and is what is available everywhere this runs.
            code = subprocess.run(
                ["curl", "-sL", "-o", "/dev/null", "-w", "%{http_code}",
                 "--max-time", "20", url],
                capture_output=True, text=True).stdout.strip() or "no reply"
            flag = "" if code == "200" else "  <-- check"
            print("%-6s %s%s" % (code, url, flag))
            if code != "200":
                broken.append((url, url, "external %s" % code))
    else:
        print()
        for url in sorted(external):
            print("extern  %s" % url)

    print("\n%d pages, %d external links, %d broken"
          % (len(ids), len(external), len(broken)))
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
