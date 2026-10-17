# Untangled for PHP

The PHP library and CLI of [Untangled](../README.md). It scans a Composer
project into the [pairs document](../spec/pairs-format.md) defined by the
shared spec, and analyzes it for cycles and coupling ([metrics](../spec/metrics.md),
[clustering](../spec/clustering.md)). The HTML report comes next.

Requires PHP 8.2+ and uses [nikic/PHP-Parser](https://github.com/nikic/PHP-Parser).

## Usage

```sh
composer install
bin/untangled scan /path/to/project            # pairs document as JSON
bin/untangled scan /path/to/project --dev      # include autoload-dev (tests)
bin/untangled scan /path/to/project --format=snakefood --output=deps.txt

bin/untangled analyze /path/to/project                      # cycles and metrics per file
bin/untangled analyze /path/to/project --cluster=namespace:2
bin/untangled analyze /path/to/project --cluster=folder:2 --exclude='src/Legacy/**'
bin/untangled analyze /path/to/project --cluster=rules:clusters.rules
bin/untangled analyze pairs.json --cluster=namespace:2      # a saved pairs document
```

`analyze` writes the [analysis document](../spec/metrics.md#the-analysis-document):
fan-in, fan-out, instability and external / unresolved counts per unit, Ca and
Ce per cluster, every dependency cycle with one example loop, and a project
summary. `--include` and `--exclude` take globs on file paths, can be repeated,
and the last matching one wins.

`utg` is a short alias for `untangled`.

## What it reads

The full rules are in the [PHP profile](../spec/languages/php.md). In short:

- The project must have a `composer.json`. Its `autoload` rules (`psr-4`,
  `psr-0`, `classmap`, `files`) decide which files are scanned; `vendor/` never is.
- `include` / `require` with a literal path (string literals, `__DIR__`,
  `dirname()`) are followed, and the included file is scanned too. Paths
  built at runtime are reported as unresolved.
- Every class reference resolves to a project file, a Composer package (from
  `vendor/composer/installed.json` or `composer.lock`), a PHP builtin, or an
  unresolved node.

## Development

```sh
composer install
composer test
```

`composer test` runs PHPUnit (a dev dependency in `composer.json`). The suite
has one test file per class under `tests/`, mirroring `src/`, plus
`tests/ConformanceTest.php`, which runs every shared case in
[`../conformance/cases`](../conformance/README.md). Tests that need files on
disk write a throwaway project with `tests/TempProject.php`.

## License

MIT, see [LICENSE](LICENSE).
