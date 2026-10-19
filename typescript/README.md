# Untangled for JavaScript / TypeScript

The JavaScript/TypeScript library and CLI of [Untangled](../README.md), to be
published on npm as `@krazybean/untangled`. It scans a JavaScript or
TypeScript project (or a mix of both) into the
[pairs document](../spec/pairs-format.md) defined by the shared spec, following
the [JavaScript and TypeScript profile](../spec/languages/typescript.md).

> **Status:** `scan` works. `analyze` and `report` are not ported yet: save the
> scan with `--output=pairs.json` and run `untangled analyze pairs.json` or
> `untangled report pairs.json` with the [PHP](../php/README.md) or
> [Python](../python/README.md) library, which read any library's pairs
> document. The package is not on npm yet.

## Install

Requires Node.js 22.18+ or 24.11+. The only runtime dependency is
[`@babel/parser`](https://babeljs.io/docs/babel-parser), which reads
JavaScript, JSX, TypeScript and Flow without needing the project's own
TypeScript compiler. The package is not on npm yet, so install it from a clone:

```sh
git clone https://github.com/krazybean/Untangled.git
cd Untangled/typescript
npm ci          # also builds dist/
node bin/untangled.js --version
```

`npm link` puts `untangled` (and its short alias `utg`) on your `PATH`.
Untangled reads the project you point it at and never runs it, so it does not
need to be installed into that project.

## scan

Writes every file-to-file dependency of the project as a
[pairs document](../spec/pairs-format.md).

```sh
untangled scan /path/to/project                          # pairs document (JSON) to stdout
untangled scan /path/to/project --output=pairs.json      # ... to a file
untangled scan /path/to/project --dev                    # include tests
untangled scan /path/to/project --format=snakefood       # snakefood's line format
```

What it scans: every `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`, `.mts` and
`.cts` file, except `node_modules/`, hidden folders, build output (`dist/`,
`build/`, `coverage/` and the tsconfig `outDir`) and tests (`*.test.*`,
`*.spec.*`, `__tests__/`, `__mocks__/`, `test/`, `tests/`). Declaration files
(`.d.ts`) and tests are scanned when a scanned file imports them.

Each import becomes an edge to:

- another project file (`./util` finds `util.ts`, `util/index.js` and so on,
  and `./util.js` finds `util.ts`, the `NodeNext` convention);
- `npm:<package>` for a package declared in `package.json` or installed in
  `node_modules/`;
- `builtin:<module>` for a Node.js builtin (`fs`, `node:fs/promises`);
- `unresolved:module:<specifier>` when none of these is found, or
  `unresolved:dynamic:<source>` for `import(name)` and `require(name)`.

Aliases are read from `package.json` `imports` (`#internal/x`) and from
`compilerOptions.paths` and `baseUrl` in `tsconfig.json` (or `jsconfig.json`),
following `extends`. Imports of non-code files (`./style.css`, `./logo.svg`)
give no edge; the scan says how many there were.

### Options

| Option | What it does |
| --- | --- |
| `--dev` | Also scan tests |
| `--source=<path>` | Scan the code files in this folder or file (relative to the project) even when they are build output or tests. Repeatable |
| `--aliases=<file.json>` | Read more aliases from a JSON file shaped like tsconfig's `paths`, with paths relative to the project root, for aliases set in webpack or Vite configuration: `{ "@/*": ["src/*"], "config": "src/config/index.ts" }`. Repeatable, and read before tsconfig |
| `--format=json\|snakefood` | `json` (default) is the pairs document; `snakefood` is snakefood's `((root, from), (root, to))` lines, internal files only |
| `--output=<file>` | Write to a file instead of standard output |

Warnings (files that do not parse, skipped build output, imports of non-code
files, packages that could not be found because `node_modules/` is missing) go
to standard error and do not change the exit code.

Exit codes: 0 on success, 1 when the project or an output cannot be read or
written, 2 for a usage error.

### Not in this version

Workspaces (a package importing another package of the same repository by
name resolves only through `node_modules/`), `exports` and `main` of packages,
project references, triple-slash `/// <reference>` directives, bundler globs
(`import.meta.glob`, `require.context`) and imports inside Vue, Svelte or Astro
files. See the [profile](../spec/languages/typescript.md) for the details.

## Development

```sh
npm ci
npm run typecheck
npm test            # unit tests and the shared conformance cases
npm run build       # dist/, used by bin/untangled.js
```

The tests run every [conformance case](../conformance/README.md) that has a
`typescript/` folder.

## License

MIT, see [LICENSE](LICENSE).
