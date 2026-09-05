#!/bin/sh
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
# Assemble assets/patternfly/patternfly-site.css from the parts of
# @patternfly/patternfly this site uses, so the page does not ship the 1.8 MB
# full bundle. Needs node and npm; nothing else does. Run from the repo root:
#
#   sh tools/patternfly/build.sh
#
# The output is committed, so the day-to-day build is Python only.
#
# The component list is the app shell PatternFly is built around — Page,
# Masthead, Nav — plus the few things the content is made of. It follows
# gahingwoo.com, which is the same shell Cockpit runs.
set -e

COMPONENTS="Page/page Masthead/masthead Button/button Card/card Backdrop/backdrop \
            DescriptionList/description-list Table/table Table/table-grid \
            Nav/nav BackToTop/back-to-top \
            SkipToContent/skip-to-content JumpLinks/jump-links \
            Brand/brand Content/content Title/title Hero/hero Accordion/accordion \
            AboutModalBox/about-modal-box \
            Avatar/avatar"
LAYOUTS="Gallery/gallery Stack/stack Grid/grid Flex/flex Bullseye/bullseye"

OUT=assets/patternfly
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

( cd "$WORK" && npm pack @patternfly/patternfly@6 >/dev/null 2>&1 && tar xzf patternfly-patternfly-*.tgz )
PKG="$WORK/package"
mkdir -p "$OUT"

{
  echo "/* Built by tools/patternfly/build.sh from @patternfly/patternfly $(node -p "require('$PKG/package.json').version"). Do not edit. */"
  cat "$PKG/patternfly-base.css"
  for c in $COMPONENTS; do cat "$PKG/components/$c.css"; done
  for l in $LAYOUTS; do cat "$PKG/layouts/$l.css"; done
} > "$OUT/patternfly-site.css"

# PatternFly's own @font-face rules resolve relative to the stylesheet, so the
# fonts go where it looks for them rather than somewhere of our choosing.
for d in RedHatDisplay RedHatText RedHatMono; do
  mkdir -p "$OUT/assets/fonts/$d"
  cp "$PKG/assets/fonts/$d/"*VF.woff2 "$PKG/assets/fonts/$d/"*VF-Italic.woff2 "$OUT/assets/fonts/$d/"
done

# The about modal's background pattern, which PatternFly points its
# --BackgroundImage variable at. Same reasoning as the fonts: it is addressed
# from inside the stylesheet, so it goes where the stylesheet expects it.
mkdir -p "$OUT/assets/images"
cp "$PKG/assets/images/pf-background.svg" "$OUT/assets/images/"

node -p "'@patternfly/patternfly ' + require('$PKG/package.json').version" > "$OUT/VERSION"
echo "components: $COMPONENTS" >> "$OUT/VERSION"
echo "layouts: $LAYOUTS" >> "$OUT/VERSION"

wc -c "$OUT/patternfly-site.css"
