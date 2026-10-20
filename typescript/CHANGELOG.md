# Changelog

All notable changes to the JavaScript/TypeScript library. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/): the pairs document, the analysis
document and the command-line options are the public interface.

## Unreleased

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
