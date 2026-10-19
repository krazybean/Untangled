# JavaScript and TypeScript profile

How the JavaScript/TypeScript library turns a project into a
[pairs document](../pairs-format.md). One profile covers both languages: a
TypeScript project imports JavaScript and the other way round, so the scanner
reads them together. `language` in the document is `typescript`.

## Input

- The project root is the folder given on the command line. No manifest is
  required. `tsconfig.json` (or `jsconfig.json`) is read at the root, and
  every `package.json` in the project (outside `node_modules/` and hidden
  folders) is read when a file under it imports a package: a repository often
  holds a frontend or a tool with its own `package.json` in a subfolder.
- **Scanned files** are the files under the root ending in `.js`, `.jsx`,
  `.mjs`, `.cjs`, `.ts`, `.tsx`, `.mts` or `.cts`, except:
  - declaration files (`.d.ts`, `.d.mts`, `.d.cts`), which are scanned only
    when a scanned file imports them;
  - files in `node_modules/` and hidden folders (name starting with `.`).
    A code file in a hidden folder that a scanned file imports by a relative
    path (`./.eslint-plugin-local`) is scanned too;
  - files in **build output** folders: any folder named `dist`, `build` or
    `coverage`, and the `compilerOptions.outDir` of `tsconfig.json`. The scan
    warns with the number of files skipped this way and the folders holding
    them, so the user can add them back with `--source`.
- **Tests** are scanned only with `--dev` (tests usually depend on
  everything, which hides the real structure): files named `*.test.*` or
  `*.spec.*`, and files in a folder named `__tests__`, `__mocks__`, `test` or
  `tests`. A test file that a scanned file imports is scanned too.
- `--source=<path>` (repeatable) is a folder or file, relative to the project
  root, whose code files are scanned even when they are in build output or are
  tests. A path that does not exist, or is outside the project, is a warning.
- JavaScript has no namespaces, so internal nodes have no `module`, and
  `--cluster=namespace:N` falls back to `folder:N` (see
  [clustering](../clustering.md)).

## Edge kinds

Each reference carries one kind for the statement, plus `type` when it only
imports types. An edge's `kinds` is the union over its references, and ambient module declarations (`declare module "x"` in a
declaration file the project includes).

| kind | meaning |
| --- | --- |
| `import` | `import x from "a"`, `import "a"`, `import * as x from "a"`, and type-level imports such as `typeof import("a")` and `import("a").T` |
| `export` | `export { x } from "a"`, `export * from "a"` |
| `require` | `require("a")`, and TypeScript's `import x = require("a")` |
| `dynamic` | `import("a")` |
| `type` | the reference only imports types: `import type`, `export type`, an import whose every name is marked `type` (`import { type A, type B }`), and type-level imports |

`require` counts when it is called by that name with at least one argument; a
local variable named `require` is not told apart. An `import()` or `require()`
whose argument is not a string literal (or a template literal without
expressions) is `unresolved:dynamic:<source text>`, the expression as written
with runs of whitespace collapsed to one space.

Not in v0.1: triple-slash `/// <reference path>` directives, `require.resolve`,
`new URL("./x", import.meta.url)`, bundler globs (`import.meta.glob`,
`require.context`), and imports in Vue, Svelte or Astro files.

## Resolving an import

A specifier is resolved in this order. A `?query` (`./icon.svg?raw`) is
dropped from a relative specifier first.

1. **Relative** (`./`, `../`, `.` or `..`): the path is joined to the importing
   file's folder, then tried as written:
   1. the file itself, when it exists;
   2. for a specifier ending in `.js`, `.jsx`, `.mjs` or `.cjs` that names no
      file, the TypeScript source it is compiled from (the `NodeNext`
      convention): `.js` tries `.ts`, `.tsx` and `.d.ts`; `.jsx` tries `.tsx`;
      `.mjs` tries `.mts` and `.d.mts`; `.cjs` tries `.cts` and `.d.cts`;
   3. the path plus each extension, in this order: `.ts`, `.tsx`, `.d.ts`,
      `.mts`, `.cts`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.json`;
   4. the path as a folder: its `index` plus each extension, in the same order.

   The first file found is the target. A `.json` file is an `internal` node
   that is not scanned. Any other file that exists but is not code
   (`./style.css`, `./logo.svg`) gives **no edge**; the scan warns with the
   number of such imports per extension, so they are not lost silently.
   When nothing is found, the target is `unresolved:module:<path>`, with
   `<path>` relative to the project root (`unresolved:module:src/missing`), so
   every file importing the same missing module points at the same node; a
   path that leaves the project is `unresolved:module:<specifier as written>`.
   A specifier starting with `/` is unresolved as written.
2. **Package imports** (`#internal/x`): the `imports` field of the nearest
   `package.json` (in the importing file's folder or the closest one above
   it), as Node.js reads it. A key matches the specifier exactly, or has one `*` that
   matches any text. Its target is a string, or an object of conditions whose
   first string value (depth first, in the order written) is used. A target
   starting with `./` is resolved from that `package.json`'s folder as in step 1; any
   other target is resolved from step 4 on. A specifier that no key matches
   goes on to step 3 (tsconfig `paths` may map `#` names too).
3. **Aliases**, from these sources in order:
   1. `--aliases=<file.json>` (repeatable), a JSON object in the shape of
      `compilerOptions.paths`, with paths relative to the project root:
      `{ "@/*": ["src/*"], "config": "src/config/index.ts" }`. It is for
      aliases that live in bundler configuration (webpack, Vite), which the
      scanner does not run.
   2. `compilerOptions.paths` of the root `tsconfig.json`, or of
      `jsconfig.json` when there is no `tsconfig.json`, following `extends`
      when it names a file in the project (TypeScript's precedence: a field
      in the extending file wins). Paths are relative to `baseUrl` when it is
      set, else to the folder of the file that declares `paths`.
   3. `compilerOptions.baseUrl`: a bare specifier joined to it.

   A key matches as in step 2; when several do, the one with the longest text
   before its `*` wins. Each of its targets is resolved as a path in step 1,
   and the first that finds a file is the target. When none does, resolution
   goes on with the next source, then the next step, as TypeScript does.
   The files are JSON with comments and trailing commas allowed.
4. **Builtin.** `node:fs` and `node:fs/promises` are `builtin:fs`. A bare
   specifier whose first segment is a Node.js builtin module (`fs`, `path`,
   `events`) is `builtin:<name>` too, unless a dependency of that name is
   declared (see step 5) for the importing file (a browser polyfill such as
   `events` or `buffer`).
   The list is fixed, Node.js 24's, so a project is classified the same on
   every Node version.
5. **Package.** A bare specifier names a package: its first segment, or its
   first two for a scoped name (`lodash/fp` is `lodash`, `@scope/pkg/x` is
   `@scope/pkg`). The target is `npm:<name>` when it is declared (in
   `dependencies`, `devDependencies`, `peerDependencies` or
   `optionalDependencies`) by the nearest `package.json` of the importing file
   or any `package.json` above that one, up to the project root; or when
   `node_modules/<name>/package.json` exists in the importing file's folder or
   any folder above it, up to the project root, as Node.js looks for packages.
   A package that ships no code and is known only by its types (`vscode`,
   provided by the host at run time) counts too: when its DefinitelyTyped
   package (`@types/<name>`, or `@types/<scope>__<name>` for `@scope/name`) is
   declared or installed the same way, the target is still `npm:<name>`.
6. Otherwise the target is `unresolved:module:<specifier>`.

The scanner warns, without failing, when the project has no `node_modules/` folder and
bare specifiers went unresolved (naming the first few), since they may be
packages that are installed but not declared.

Not in v0.1: workspaces (a package importing another package of the same
repository by name resolves only through `node_modules/`), a package importing
itself by its own name, `exports` and `main` of packages, and project
references.

## Parsing

The reference implementation uses `@babel/parser`, which reads JavaScript,
JSX, TypeScript and TSX without depending on the TypeScript compiler the
project uses. `.ts`, `.mts` and `.cts` files are read as TypeScript, `.tsx` as
TypeScript with JSX, declaration files as TypeScript declarations, and
JavaScript files as JavaScript with JSX (and again with Flow types when that
leaves syntax errors). TypeScript files are read with the legacy decorators proposal first,
which allows parameter decorators (`constructor(@inject(A) a: A)`), and
again with the current one when that leaves syntax errors; the parse with the
fewest errors is kept, as it is for the two JavaScript readings. `.cjs` files are scripts, `.mjs` files modules, and other files either,
by what they contain.

The parser recovers from most syntax errors; the imports it still finds are
kept, and the scan warns once, naming the first few such files. A file that
does not parse at all is still a node; the scanner warns with the error and
records no edges for it.

Files are decoded as UTF-8 (a BOM is dropped); a file that is not valid UTF-8
is read as Windows-1252, as [pairs-format](../pairs-format.md) requires for
names. File names that are not valid UTF-8 are read the same way.
