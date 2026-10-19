#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# Builds the PHP package as it is published on Packagist: Packagist needs
# composer.json at a repository root, so .github/workflows/php-distribution.yml
# copies this folder's output into its own repository, krazybean/krazybean-untangled-php.
#
#   scripts/export-php.sh X.Y.Z|bootstrap OUTPUT_DIR
#
# Only what `composer require` needs is exported: the library, its CLI and the
# resources it loads at runtime. Tests stay here, next to the conformance cases.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD

if [[ $# -ne 2 ]]; then
  echo "usage: $0 X.Y.Z|bootstrap OUTPUT_DIR" >&2
  exit 2
fi
VERSION=$1
OUTPUT=$2
if [[ $VERSION != bootstrap && ! $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+(-(alpha|beta|RC)[0-9]+)?$ ]]; then
  echo "invalid version: $VERSION" >&2
  exit 2
fi
if [[ -z $OUTPUT || $OUTPUT == / || $(realpath -m "$OUTPUT") == "$ROOT"* ]]; then
  echo "refusing output directory inside the repository: $OUTPUT" >&2
  exit 2
fi

inputs=(composer.json README.md CHANGELOG.md LICENSE bin src resources)
for input in "${inputs[@]}"; do
  if [[ ! -e php/$input ]]; then
    echo "missing PHP distribution input: php/$input" >&2
    exit 1
  fi
done
if find php/bin php/src php/resources -type l -print -quit | grep -q .; then
  echo "refusing symlinked inputs" >&2
  exit 1
fi

name=$(php -r 'echo json_decode(file_get_contents("php/composer.json"), true, 512, JSON_THROW_ON_ERROR)["name"];')
if [[ $name != krazybean/untangled ]]; then
  echo "composer package name must be krazybean/untangled, not $name" >&2
  exit 1
fi
declared=$(php -r 'require "php/src/Version.php"; echo Untangled\Version::VERSION;')
if [[ $VERSION != bootstrap && $declared != "$VERSION" ]]; then
  echo "php/src/Version.php says $declared, not $VERSION" >&2
  exit 1
fi

if [[ -e $OUTPUT ]] && find "$OUTPUT" -mindepth 1 -print -quit | grep -q .; then
  echo "output directory must be empty: $OUTPUT" >&2
  exit 1
fi
mkdir -p "$OUTPUT"
for input in "${inputs[@]}"; do
  cp -R "php/$input" "$OUTPUT/$input"
done
# The test setup refers to files that are not exported.
php -r '
$path = $argv[1] . "/composer.json";
$composer = json_decode(file_get_contents($path), true, 512, JSON_THROW_ON_ERROR);
unset($composer["require-dev"], $composer["autoload-dev"], $composer["scripts"]);
file_put_contents($path, json_encode($composer, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "\n");
' "$OUTPUT"

echo "Prepared the PHP package ($VERSION) in $OUTPUT"
