#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# The HTML report's script and styles are shared by every library: php/resources/report
# is the source, and the other libraries carry verbatim copies (which keep their MIT
# header). This copies them over; with --check it only fails when a copy is out of date.
set -euo pipefail
cd "$(dirname "$0")/.."

source=php/resources/report
copies=(python/src/untangled/report/assets)
status=0

for target in "${copies[@]}"; do
  for name in report.js report.css; do
    if [[ ${1:-} == --check ]]; then
      if ! cmp -s "$source/$name" "$target/$name"; then
        echo "out of date: $target/$name (run scripts/sync-report-assets.sh)"
        status=1
      fi
    else
      mkdir -p "$target"
      cp "$source/$name" "$target/$name"
    fi
  done
done

if [[ ${1:-} == --check && $status == 0 ]]; then
  echo "report assets ok"
fi
exit $status
