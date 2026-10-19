#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# Regenerates the demo reports and graphs in docs/examples/ (shown in
# EXAMPLES.md) from this checkout's libraries. The outside projects are cloned
# at pinned commits into a temporary folder, so the examples only change when
# Untangled does.
#
#   scripts/make-examples.sh
#
# Needs php (with `composer install` run in php/), python3 >= 3.11 and git.
# Graphviz `dot` is used to draw the classic graphs as SVG when it is
# installed; without it only the .dot files are written. The JS/TS example is
# skipped until typescript/ is built (`npm ci` in typescript/). The PNG
# screenshots are taken by hand: open each report at 1280x900 in a browser.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
OUT=$ROOT/docs/examples
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

MONICA_COMMIT=6e6ec217457e946e330ba7cd3b28107f4332c7b1
MAILRECON_COMMIT=4917ce8a636d384b77971badaa9607a20beefded
SPECTRA_COMMIT=7e05c36b7a3a46804c234b972b6b1e1f8c287eef

php_untangled() { php "$ROOT/php/bin/untangled" "$@"; }
py_untangled() { PYTHONPATH="$ROOT/python/src" python3 -m untangled "$@"; }

clone() { # clone <github repo> <commit> <folder>
  git init -q "$3"
  git -C "$3" fetch -q --depth 1 "https://github.com/$1" "$2"
  git -C "$3" checkout -q FETCH_HEAD
}

svg() { # svg <name>: draw docs/examples/<name>.dot as <name>.svg
  if command -v dot >/dev/null; then
    dot -Tsvg "$OUT/$1.dot" > "$OUT/$1.svg"
  else
    echo "dot not installed: left $1.svg as it was" >&2
  fi
}

mkdir -p "$OUT"

# The layers fixture: a small project with a known shape.
php_untangled report conformance/cases/layers/php/project --title="Sample: layers fixture" \
  --output="$OUT/fixture-layers-report.html"

# Untangled's own PHP library.
php_untangled report php --title="Untangled PHP library" --output="$OUT/php-untangled-report.html"
php_untangled report php --format=dot --style=classic --output="$OUT/php-untangled-classic.dot"
svg php-untangled-classic

# Monica, a Laravel CRM with real cycles.
clone monicahq/monica "$MONICA_COMMIT" "$WORK/monica"
monica=(--source=routes --source=config --source=database/migrations --source=bootstrap --aliases=laravel)
php_untangled report "$WORK/monica" "${monica[@]}" --cluster=namespace:3 --title="Monica" \
  --output="$OUT/php-monica-report.html"
php_untangled report "$WORK/monica" "${monica[@]}" --cluster=namespace:2 --format=dot --style=classic \
  --output="$OUT/php-monica-classic.dot"
svg php-monica-classic

# mailrecon, a small Python CLI.
clone krazybean/mailrecon "$MAILRECON_COMMIT" "$WORK/mailrecon"
py_untangled report "$WORK/mailrecon" --output="$OUT/python-mailrecon-report.html"
py_untangled report "$WORK/mailrecon" --format=dot --style=classic --output="$OUT/python-mailrecon-classic.dot"
svg python-mailrecon-classic

# spectra, a Next.js app with Node scripts.
if [[ -d typescript/dist ]]; then
  clone krazybean/spectra "$SPECTRA_COMMIT" "$WORK/spectra"
  node typescript/bin/untangled.js report "$WORK/spectra" --output="$OUT/js-spectra-report.html"
  node typescript/bin/untangled.js report "$WORK/spectra" --format=dot --style=classic \
    --output="$OUT/js-spectra-classic.dot"
  svg js-spectra-classic
else
  echo "typescript/ is not built: left the spectra example as it was" >&2
fi

echo "examples written to docs/examples/"
