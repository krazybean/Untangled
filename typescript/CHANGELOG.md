# Changelog

All notable changes to the JavaScript/TypeScript library. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/): the pairs document, the analysis
document and the command-line options are the public interface.

## Unreleased

- `dependents --max-depth=N` (with `--transitive`) stops the walk after N steps from the
  targets, and `--through=<glob>` (repeatable) only walks into files that match, so a
  test that reaches a target only through application code is not found by way of it.
  `--include` and `--exclude` still filter the list afterwards. `--max-depth` without
  `--transitive`, or not a positive integer, is a usage error. See spec/dependents.md.

- `dependents` accepts an absolute path inside the project, and a path written with `./`
  or `\`. An absolute path outside the project is an error rather than a lookup that
  finds nothing.

- Globs with a hyphen in the pattern (`--exclude=src/user-controller.ts`) no longer make
  the command fail: the hyphen was escaped in a way the regular expression rejected.

## 1.0.2

- New `dependents` command: lists the files that depend on one or more files
  (or declared symbols), directly or with `--transitive` through other files,
  with each one's depth. It reads a project or a pairs document, accepts
  `--include` / `--exclude`, and writes text grouped by folder or
  `--format=json`. See spec/dependents.md.

- `analyze` and `report` warn on standard error when `--cluster=rules:<file>`
  leaves files unmatched (each becomes its own cluster), naming the first few.
  `--strict` makes that an error: exit code 1 and no output, for CI. Before,
  a new top-level folder that no rule named dropped out of the grouped view
  without a sign.

## 1.0.1

- `scan` marks a file that does not parse, or cannot be read, with
  `"error": "parse"` or `"error": "read"` in the pairs document, and the
  HTML report counts and lists those files under "Files we could not read".
  Before, such a file looked like one with no dependencies.
- `scan` warns when it finds no files to scan, instead of writing an empty
  document silently.
- The warning about a missing `node_modules/` no longer suggests that
  installing will resolve every name it lists. Ambient module declarations
  (`declare module "x"`) are documented as not followed.
- Package metadata: registry keywords now name code dependencies directly
  (code dependencies, circular dependencies, import graph, module
  dependencies), so the package is findable by what it analyzes.

## 1.0.0

First release.

- `scan`: parses every JavaScript, TypeScript, JSX and Flow file with
  `@babel/parser` and resolves imports as Node.js and TypeScript do: relative
  paths (including the `NodeNext` `.js` convention), `package.json`
  `imports`, tsconfig `paths` and `baseUrl` (following `extends`),
  `--aliases` files for bundler aliases, Node.js builtins, and packages
  declared in any `package.json` up the tree or installed in `node_modules/`
  (including packages known only by their `@types/` package). Writes the
  pairs document, or snakefood's format with `--format=snakefood`.
- `analyze` and `report`: the same analyses, HTML report and DOT graphs as
  the PHP and Python libraries, including `--style=classic`.
- Checked on VS Code, typescript-eslint, Express and Next.js Commerce.
