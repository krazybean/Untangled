# js-aliases

Aliases from `--aliases` (`typescript/aliases` lists `bundler-aliases.json`) and
from `tsconfig.json`, which extends `config/tsconfig.base.json` (and a package
config, `@tsconfig/node22`, which is not read). Both files have comments and
trailing commas. The base file has no `baseUrl`, so its `paths` are relative to
`config/`.

- `@components/panel` and `config` come from the `--aliases` file.
- `@/first` is in the `--aliases` file's `src/shadowed/`, which is tried before
  tsconfig; `@/domain/models/user` is not, so it goes on to tsconfig's `src/*`.
- `@app/models/order` matches both `@app/*` and `@app/models/*`; the longer
  prefix wins.
- `~/api/client` is found in the first target, `generated/`; `~/theme` only in
  the second, `src/`.
- `logger` is an exact key naming a file.
- `@/nope` matches aliases that name no file and is not a package:
  `unresolved:module:@/nope`.
