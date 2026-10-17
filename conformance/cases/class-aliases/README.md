# class-aliases

Global class aliases that a framework registers at runtime, declared with
`--aliases` (the `aliases` file lists `laravel` and `aliases.json`):

- `DB` and `Redirect`, imported with `use DB;` and used statically, come from
  the `laravel` preset and resolve to `laravel/framework`, as their facades do.
- `\Cart` is an alias that the `acme/cart` package declares under
  `extra.laravel.aliases`, which the preset reads.
- `aliases.json` maps `Money` to a project class, so `\Money` is an edge to
  `src/Money.php`, and maps `Log` to `Acme\Logging\Log`, overriding the
  preset. No package provides that class, so the target is unresolved under
  the aliased name.
- `\Telescope` is declared by no one and stays unresolved.
