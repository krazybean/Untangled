# Changelog

All notable changes to the JavaScript/TypeScript library. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/): the pairs document, the analysis
document and the command-line options are the public interface.

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
