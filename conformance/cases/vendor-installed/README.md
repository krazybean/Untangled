# vendor-installed

With `vendor/` installed, packages come from `vendor/composer/installed.json`.
A package that autoloads through a `classmap` is resolved by reading the
classes its files declare. An include that lands inside `vendor/` points at
the package, and `vendor/` itself is never scanned, so functions declared
there (`acme_slug`) are not edges.
