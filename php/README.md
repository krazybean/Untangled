# Untangled for PHP

The PHP library and CLI of [Untangled](../README.md). It scans a Composer
project into the [pairs document](../spec/pairs-format.md) defined by the
shared spec. Analysis (cycles, clustering, metrics) and the HTML report come
next.

Requires PHP 8.2+ and uses [nikic/PHP-Parser](https://github.com/nikic/PHP-Parser).

## Usage

```sh
composer install
bin/untangled scan /path/to/project            # pairs document as JSON
bin/untangled scan /path/to/project --dev      # include autoload-dev (tests)
bin/untangled scan /path/to/project --format=snakefood --output=deps.txt
```

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

`composer test` runs `tests/run.php`, which runs the shared conformance cases in
[`../conformance/cases`](../conformance/README.md) plus unit checks.

## License

MIT, see [LICENSE](LICENSE).
