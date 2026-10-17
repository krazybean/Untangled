# layers

A small layered app with three namespaces (`App\Domain`, `App\Infra`,
`App\Http`) and a `bootstrap.php` with no namespace at the project root.

- **File graph:** one cycle, `Router ↔ UserController`, both in `App\Http`.
- **`namespace:2`:** that cycle is inside one cluster and disappears, while a
  cycle between clusters appears, `App\Domain ↔ App\Infra`
  (`User → Clock`, `UserRepository → User`), which no file cycle shows.
  `bootstrap.php` has no namespace, so it falls back to its folder, `.`.
- **`folder:1`:** everything under `src/` is one cluster; `bootstrap.php` is in `.`.
- **`rules`** (`php/clusters.rules`): `Web` has `fan_out` 1 (one cluster) but
  `ce` 2 (two files in `Core`), which is why Ca / Ce count files.
  `bootstrap.php` matches no rule and is its own cluster.
- `UserRepository` uses `App\Cache\Store`, which does not exist: one unresolved
  reference. `Clock` uses `DateTimeImmutable`, a builtin, which the default
  filter drops before analysis.
