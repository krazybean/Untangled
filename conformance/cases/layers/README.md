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
- **`dependents`** (`<language>/dependents.<name>.args`): who depends on `User`,
  directly (`direct`) and through other files (`transitive`, which shows the
  `Router` / `UserController` cycle listed once at its shortest depth, and
  `bootstrap` at depth 4); the text form grouped by folder (`text`); two targets
  at once, with `UserController` listed once (`multi`); and `--exclude=**
  --include=<http folder>` (`filtered`), where only the `http` files are listed
  but the walk still goes through `domain` and `infra`. PHP asks for `User` by its
  class name too; Python and TypeScript nodes declare no symbols, so they use files.
  `--max-depth` and `--through` limit the walk: `max-depth-1`, `-2`, `-large` and
  `-text` stop at a depth; `through-barrier` allows the `domain` files only, so
  `UserRepository` (in `infra`) and `UserController` (in `http`, which reaches
  `User` by way of `Order`) are not found, only `Order`; `through-multi` has two
  patterns; `through-depth` adds `--max-depth=2`; `through-filter` shows that
  `--exclude` hides `UserController` from the list while the walk still goes
  through it; `through-start` begins at `Clock`, which `--through` does not match;
  `through-multitarget` has two targets and the `Router` / `UserController`
  cycle; `through-direct` has no `--transitive`; `through-none` matches nothing.
  PHP also has `backslash`, a class name written with a leading `\`.
- `UserRepository` uses `App\Cache\Store`, which does not exist: one unresolved
  reference. `Clock` uses `DateTimeImmutable`, a builtin, which the default
  filter drops before analysis.

The Python version (`python/`) has the same shape, with the packages
`app.domain`, `app.infra` and `app.http` under `src/` and `bootstrap.py` at the
project root, and its own `python/clusters.rules`. Its analyses have the same
summaries as PHP's. With `namespace:2`, `bootstrap.py` has the module
`bootstrap`, so it keeps that one segment as its cluster instead of falling back
to `.`. `app.cache.store` does not exist (one unresolved reference) and
`datetime` is a builtin.

The TypeScript version (`typescript/`) has the same shape, with the folders
`src/domain`, `src/infra` and `src/http` and `bootstrap.ts` at the project
root, and its own `typescript/clusters.rules`. JavaScript has no namespaces, so
`namespace:2` falls back to `folder:2`, which gives the same clusters, and
`bootstrap.ts` is in `.` as in PHP. `../cache/store.js` does not exist (one
unresolved reference, `unresolved:module:src/cache/store.js`) and
`node:perf_hooks` is a builtin.
