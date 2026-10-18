# Untangled for Python

The Python library and CLI of [Untangled](../README.md), to be published on
PyPI as `untangled`. It scans a Python project into the
[pairs document](../spec/pairs-format.md) defined by the shared spec, following
the [Python profile](../spec/languages/python.md).

Untangled is a re-imagining of [snakefood](https://github.com/blais/snakefood)
by Martin Blais, and this library is its most direct successor: it parses every
file, collects its imports and resolves them against the project's import
roots, without running any of its code. See
[Credit](../README.md#credit-snakefood).

> **Status:** `scan`, `analyze` and `report` work, and give the same analyses,
> HTML reports and DOT graphs as the PHP library for the same pairs document.
> The package is not on PyPI yet.

## Install

Requires Python 3.11+, and nothing else: the scanner uses Python's own `ast`
module. The package is not on PyPI yet, so install it from a clone:

```sh
git clone https://github.com/krazybean/Untangled.git
pip install ./Untangled/python
untangled --version
```

`utg` is a short alias for `untangled`, and `python -m untangled` works too.
Untangled reads the project you point it at and never imports or runs it, so
it does not need to be installed into that project's virtualenv. Run it with
the newest Python you have: it can only parse code written for the Python it
runs on or older.

## Commands

```
untangled scan    [<path>]               [scan options] [--format=json|snakefood] [--output=<file>]
untangled analyze [<path>|<pairs.json>]  [scan options] [filter options] [--output=<file>]
untangled report  [<path>|<pairs.json>]  [scan options] [filter options]
                                         [--format=html|dot] [--style=classic] [--title=<text>] [--output=<file>]
```

Each command runs the steps before it: `analyze` scans first, and `report`
scans and analyzes first. `analyze` and `report` also accept a pairs document
saved by `scan` (from this library or any other Untangled library), so a large
project can be scanned once and analyzed many ways. `untangled --help` prints
the same summary.

### scan

Writes every file-to-file dependency of the project as a
[pairs document](../spec/pairs-format.md).

```sh
untangled scan /path/to/project                          # pairs document (JSON) to stdout
untangled scan /path/to/project --output=pairs.json      # ... to a file
untangled scan /path/to/project --dev                    # include tests
untangled scan /path/to/project --format=snakefood       # snakefood's format, for sfood-* tools
```

### analyze

Writes cycles and coupling metrics as JSON (the
[analysis document](../spec/metrics.md#the-analysis-document)): a summary,
per-unit fan-in, fan-out and instability, and every dependency cycle with one
example loop.

```sh
untangled analyze /path/to/project                          # per file
untangled analyze /path/to/project --cluster=namespace:2    # per package path, e.g. shop.billing
untangled analyze /path/to/project --cluster=folder:2 --exclude='src/shop/legacy/**'
untangled analyze pairs.json --cluster=namespace:2          # from a saved scan
```

What each number means, and why it matters, is in [metrics](../spec/metrics.md).

### report

Writes one self-contained HTML page meant for people who do not read code: a
summary in plain words, an interactive map of the dependencies, each cycle
written out as a loop, the parts to look at first, and every metric with a
short explanation. It needs no network access to open.

```sh
untangled report /path/to/project --output=report.html
untangled report /path/to/project --cluster=namespace:2 --title="Billing" --output=report.html
untangled report /path/to/project --format=dot | dot -Tsvg > graph.svg
untangled report /path/to/project --format=dot --style=classic | dot -Tpng > graph.png
```

`--format=dot` writes a Graphviz file instead, with units in a cycle drawn in
red. `--style=classic` draws the black and white look of snakefood's
`sfood-graph`.

### Options

| Option | Meaning |
| --- | --- |
| `--dev` | Also scan tests: `test/` and `tests/` folders, `test_*.py`, `*_test.py`, `conftest.py`. Tests usually depend on everything, which hides the real structure. |
| `--source=PATH` | Add a folder, relative to the project, to the import roots (repeatable), for code importable from a folder the scanner does not find by itself. |
| `--venv=PATH` | Read installed packages from this virtualenv instead of the ones found in the project (repeatable). |
| `--format=FORMAT` | `scan`: `json` (the pairs document, default) or `snakefood`. `report`: `html` (default) or `dot`. |
| `--style=classic` | `report --format=dot` only: snakefood's black and white look. |
| `--title=TEXT` | `report` only: the report's title. Defaults to the project name in `pyproject.toml`, else the folder name. |
| `--cluster=STRATEGY` | `analyze`, `report`: group files into units. `namespace:N` keeps the first N segments of the module name (`shop.billing.invoice` → `shop.billing` with N=2), `folder:N` the first N folders, and `rules:<file>` reads `<prefix> <cluster>` lines from a file, the first matching path prefix wins. See [clustering](../spec/clustering.md). |
| `--include=GLOB`, `--exclude=GLOB` | `analyze`, `report`: keep or drop project files by path (repeatable, the last matching pattern wins). `*` stays within a folder, `**` crosses folders. |
| `--output=FILE` | Write to a file instead of standard output. |

## What it reads

- **Files:** every `.py` file under the project folder, except virtualenvs,
  hidden folders, `__pycache__`, `node_modules`, `site-packages`,
  `*.egg-info`, and `build/` and `dist/` at the top. Tests only with `--dev`,
  unless real code imports them.
- **Import roots:** the project folder, `src/` (the src layout), the folders
  `pyproject.toml` gives setuptools, and `--source` folders.
- **Packages:** the project's virtualenv (any folder in it with a
  `pyvenv.cfg`, such as `.venv/`), read from each installed distribution's
  `RECORD`, so `import yaml` is `pypi:pyyaml`. Without one, an import matches a
  dependency declared in `pyproject.toml` or `requirements*.txt` only when the
  names are equal.

Every import ends up as a project file, a standard library module
(`builtin:os`), a package (`pypi:requests`) or an unresolved reference
(`unresolved:module:...`). The scanner never guesses: an import of a module
that does not exist is unresolved, never an edge to its parent package. The
[Python profile](../spec/languages/python.md) has the full rules.

## Exit codes and warnings

`0` on success, `1` when the project folder does not exist, a pairs document
or rules file cannot be read, or the output cannot be written, `2` for a usage
error. Warnings go to standard error and
do not change the exit code: a file that does not parse (such as Python 2
code), a `--source` or `--venv` that does not exist, and unresolved imports
of modules outside the project when no virtualenv was found.

## Development

```sh
cd python
python -m pip install -e . --group dev
pytest
ruff check . && ruff format --check .
```

The tests include the shared [conformance cases](../conformance/README.md)
that have a `python/` folder.

## License

GPL-2.0-only, see [LICENSE](LICENSE). This folder may port code from
snakefood, which is GPL, so code here must never be copied into the
MIT-licensed folders.
