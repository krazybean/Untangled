# Changelog

All notable changes to the Python library. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/): the pairs document, the analysis
document and the command-line options are the public interface.

## Unreleased

- New `dependents` command: lists the files that depend on one or more files
  (or declared symbols), directly or with `--transitive` through other files,
  with each one's depth. It reads a project or a pairs document, accepts
  `--include` / `--exclude`, and writes text grouped by folder or
  `--format=json`. See spec/dependents.md.

## 1.0.1

- `scan` marks a file that does not parse, or cannot be read, with
  `"error": "parse"` or `"error": "read"` in the pairs document, and the
  HTML report counts and lists those files under "Files we could not read".
  Before, such a file looked like one with no dependencies.
- `scan` warns when it finds no files to scan, instead of writing an empty
  document silently.
- Package metadata: registry keywords now name code dependencies directly
  (code dependencies, circular dependencies, import graph, module
  dependencies), so the package is findable by what it analyzes.

## 1.0.0

First release.

- `scan`: parses every file with Python's own `ast` and resolves imports
  against the project's import roots (flat and `src/` layouts, namespace
  packages, `--source`), the standard library, and installed packages from
  the project's virtualenv (`--venv`) or its declared dependencies. Files
  with syntax newer than the running Python are read statement by statement.
  Writes the pairs document, or snakefood's format with `--format=snakefood`.
- `analyze` and `report`: the same analyses, HTML report and DOT graphs as
  the PHP library, including `--style=classic`.
