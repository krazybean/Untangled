# Changelog

All notable changes to the Python library. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/): the pairs document, the analysis
document and the command-line options are the public interface.

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
