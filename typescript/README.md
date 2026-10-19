# Untangled for JavaScript / TypeScript

The JavaScript/TypeScript library and CLI of [Untangled](https://github.com/krazybean/Untangled/blob/main/README.md), published
on npm as `@krazybean/untangled`. It scans a JavaScript or
TypeScript project (or a mix of both) into the
[pairs document](https://github.com/krazybean/Untangled/blob/main/spec/pairs-format.md) defined by the shared spec, following
the [JavaScript and TypeScript profile](https://github.com/krazybean/Untangled/blob/main/spec/languages/typescript.md).

It gives the same analyses, HTML reports and DOT graphs as the PHP and Python
libraries for the same pairs document. See what they look like in the
[examples](https://github.com/krazybean/Untangled/blob/main/EXAMPLES.md).

## Install

Requires Node.js 22.18+ or 24.11+. The only runtime dependency is
[`@babel/parser`](https://babeljs.io/docs/babel-parser), which reads
JavaScript, JSX, TypeScript and Flow without needing the project's own
TypeScript compiler.

```sh
npm install -g @krazybean/untangled     # or: npx @krazybean/untangled --help
untangled --version
```

`utg` is a short alias for `untangled`.
Untangled reads the project you point it at and never runs it, so it does not
need to be installed into that project.

## Commands

```
untangled scan    [<path>]               [scan options] [--format=json|snakefood] [--output=<file>]
untangled analyze [<path>|<pairs.json>]  [scan options] [filter options] [--output=<file>]
untangled report  [<path>|<pairs.json>]  [scan options] [filter options]
                                         [--format=html|dot] [--style=classic] [--title=<text>] [--output=<file>]
```

`analyze` scans first and `report` scans and analyzes first. Both also read a
pairs document saved by `scan`, from this library or any other Untangled
library. `untangled --help` prints the same summary.

### scan

Writes every file-to-file dependency of the project as a
[pairs document](https://github.com/krazybean/Untangled/blob/main/spec/pairs-format.md).

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
(`.d.ts`), tests and files in hidden folders are scanned when a scanned file
imports them.

Each import becomes an edge to:

- another project file (`./util` finds `util.ts`, `util/index.js` and so on,
  and `./util.js` finds `util.ts`, the `NodeNext` convention);
- `npm:<package>` for a package declared in `package.json` or installed in
  `node_modules/`, or known only by its types (`vscode` with `@types/vscode`);
- `builtin:<module>` for a Node.js builtin (`fs`, `node:fs/promises`);
- `unresolved:module:<specifier>` when none of these is found, or
  `unresolved:dynamic:<source>` for `import(name)` and `require(name)`.

Aliases are read from `package.json` `imports` (`#internal/x`) and from
`compilerOptions.paths` and `baseUrl` in `tsconfig.json` (or `jsconfig.json`),
following `extends`. Imports of non-code files (`./style.css`, `./logo.svg`)
give no edge; the scan says how many there were.

### analyze

Writes cycles and coupling metrics as JSON (the
[analysis document](https://github.com/krazybean/Untangled/blob/main/spec/metrics.md#the-analysis-document)): a summary,
fan-in, fan-out and instability per unit, and every dependency cycle with one
example loop.

```sh
untangled analyze /path/to/project                          # per file
untangled analyze /path/to/project --cluster=folder:2       # per folder, e.g. src/components
untangled analyze /path/to/project --exclude='**/*.stories.tsx'
untangled analyze pairs.json --cluster=folder:2             # from a saved scan
```

### report

Writes one self-contained HTML page for people who do not read code: a
summary in plain words, an interactive map, each cycle written out as a loop,
the parts to look at first, and every metric explained. It opens offline.

```sh
untangled report /path/to/project --output=report.html
untangled report /path/to/project --cluster=folder:2 --title="Web app" --output=report.html
untangled report /path/to/project --format=dot | dot -Tsvg > graph.svg
untangled report /path/to/project --format=dot --style=classic | dot -Tpng > graph.png
```

`--format=dot` writes a Graphviz graph instead, with cycles in red;
`--style=classic` draws snakefood's black and white `sfood-graph` look.

### Options

| Option | What it does |
| --- | --- |
| `--dev` | Also scan tests |
| `--source=<path>` | Scan the code files in this folder or file (relative to the project) even when they are build output or tests. Repeatable |
| `--aliases=<file.json>` | Read more aliases from a JSON file shaped like tsconfig's `paths`, with paths relative to the project root, for aliases set in webpack or Vite configuration: `{ "@/*": ["src/*"], "config": "src/config/index.ts" }`. Repeatable, and read before tsconfig |
| `--format=<format>` | `scan`: `json` (default, the pairs document) or `snakefood` (snakefood's `((root, from), (root, to))` lines, internal files only). `report`: `html` (default) or `dot` |
| `--style=classic` | `report --format=dot` only: snakefood's black and white look |
| `--title=<text>` | `report` only: the title. Defaults to the `name` in `package.json`, else the folder name |
| `--cluster=<strategy>` | `analyze`, `report`: group files into units. `folder:N` keeps the first N folders, and `rules:<file>` reads `<prefix> <cluster>` lines, where the first matching path prefix wins. JavaScript has no namespaces, so `namespace:N` is the same as `folder:N`. See [clustering](https://github.com/krazybean/Untangled/blob/main/spec/clustering.md) |
| `--include=<glob>`, `--exclude=<glob>` | `analyze`, `report`: keep or drop project files by path (repeatable, the last matching pattern wins). `*` stays within a folder, `**` crosses folders |
| `--output=<file>` | Write to a file instead of standard output |

Warnings (files that do not parse, skipped build output, imports of non-code
files, packages that could not be found because `node_modules/` is missing) go
to standard error and do not change the exit code.

Exit codes: 0 on success, 1 when the project, a pairs document or a rules
file cannot be read or an output cannot be written, 2 for a usage error.

### Not in this version

Workspaces (a package importing another package of the same repository by
name resolves only through `node_modules/`), `exports` and `main` of packages,
project references, triple-slash `/// <reference>` directives, bundler globs
(`import.meta.glob`, `require.context`) and imports inside Vue, Svelte or Astro
files. See the [profile](https://github.com/krazybean/Untangled/blob/main/spec/languages/typescript.md) for the details.

## Development

```sh
npm ci
npm run typecheck
npm test            # unit tests and the shared conformance cases
npm run build       # dist/, used by bin/untangled.js
```

The tests run every [conformance case](https://github.com/krazybean/Untangled/blob/main/conformance/README.md) that has a
`typescript/` folder, and check the analyses and graphs of the PHP and Python
cases from their pairs documents. The report's script and styles in `assets/`
are copies of `php/resources/report/`: edit those and run
`scripts/sync-report-assets.sh`.

## License

MIT, see [LICENSE](https://github.com/krazybean/Untangled/blob/main/typescript/LICENSE).
