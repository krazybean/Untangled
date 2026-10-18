# js-packages

Bare specifiers in `src/app.ts`:

- Declared in `package.json`, in any of `dependencies`, `devDependencies`,
  `peerDependencies` and `optionalDependencies`: `npm:<name>`, where a subpath
  names its package (`lodash/map` is `npm:lodash`, `@scope/ui/button` is
  `npm:@scope/ui`).
- `installed-only` is not declared but has `node_modules/installed-only/package.json`.
- `left-pad` and `@nobody/pkg/deep` are neither: unresolved as written.
- `node:fs/promises` is `builtin:fs`, `path` and `events` are builtins without
  `node:`, and `node:test` exists only with `node:`. `buffer` is a builtin name
  too, but `package.json` declares a package of that name, so it is `npm:buffer`.
- Package imports from `package.json`'s `imports`: `#utils/slug` matches
  `#utils/*` and `#config` matches exactly, both naming files; `#date` takes the
  first string of its conditions, `date-fns`, a package; `#gone` names a file
  that does not exist (`unresolved:module:src/gone.ts`), and no key matches
  `#nothing`.
- `tools/` has its own `package.json`. `tools/src/cli.ts` gets `commander`
  (declared there), `chalk` (in `tools/node_modules/`), `react` (declared by
  the root `package.json`, above it) and `#helpers` from its own `imports`, but
  not the root's `#config`, which is unresolved there. From `src/app.ts`,
  `commander` and `chalk` are unresolved.
