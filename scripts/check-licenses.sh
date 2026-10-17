#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# Checks the split license (see LICENSE): every licensed folder has a LICENSE
# file, and every source file carries the SPDX header of the folder it is in.
# This is what keeps GPL code out of the MIT folders.
set -euo pipefail
cd "$(dirname "$0")/.."

declare -A license=(
  [php]=MIT [typescript]=MIT [spec]=MIT [conformance]=MIT [docs]=MIT
  [python]=GPL-2.0-only
)
status=0

for folder in "${!license[@]}"; do
  if [[ -d $folder && ! -f $folder/LICENSE ]]; then
    echo "missing: $folder/LICENSE"
    status=1
  fi
done

while IFS= read -r file; do
  top=${file%%/*}
  [[ $top == "$file" ]] && top=.
  expected=${license[$top]:-MIT}
  header=$(head -n 5 "$file" | grep -o 'SPDX-License-Identifier: [A-Za-z0-9.+-]*' | head -n 1 || true)
  if [[ -z $header ]]; then
    echo "no SPDX header ($expected expected): $file"
    status=1
  elif [[ ${header#SPDX-License-Identifier: } != "$expected" ]]; then
    echo "wrong license (${header#SPDX-License-Identifier: }, $expected expected): $file"
    status=1
  fi
done < <(git ls-files --cached --others --exclude-standard \
  '*.php' '*.ts' '*.mts' '*.cts' '*.js' '*.mjs' '*.cjs' '*.py' '*.sh' '*.toml' '*.yml' '*.yaml' 'php/bin/*' \
  | sort -u)

if (( status == 0 )); then
  echo "licenses ok"
fi
exit $status
