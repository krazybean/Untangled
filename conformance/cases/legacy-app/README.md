# legacy-app

An older application whose classes live in `lib/`, which `composer.json` does
not autoload (the application has its own autoloader and `include_path`). The
scan passes `--source=lib` (see `php/sources`):

- `lib/` files are scanned, so `Legacy_Order` resolves to its file and a
  missing `Legacy_Unknown` is unresolved.
- `require_once 'Legacy/helpers.php'` is found through the `lib` folder, as
  `include_path` would find it.
- `lib/Legacy/Cafe.php` is saved as Latin-1 and declares `Café`; the
  document carries the name as UTF-8.
- The installed `acme/polyfill` declares `Stringable` for old PHP versions;
  the builtin wins, so it is `builtin:Stringable`.
- `vendor/autoload.php` is not recorded, and `Composer\InstalledVersions` is
  `composer:composer-runtime-api`.
- `lib/Legacy/Broken.php` does not parse, so it is a node with
  `"error": "parse"` and no edges.
- `scripts/cron.php` is neither autoloaded nor a `--source`, so it is not
  scanned (the scanner warns about it).
