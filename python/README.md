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

> **Status:** `scan` works. `analyze` and `report` come next; until then, the
> PHP library's `untangled analyze pairs.json` and `untangled report pairs.json`
> read this library's pairs documents.

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

## scan

```sh
untangled scan /path/to/project                          # pairs document (JSON) to stdout
untangled scan /path/to/project --output=pairs.json      # ... to a file
untangled scan /path/to/project --dev                    # include tests
untangled scan /path/to/project --format=snakefood       # snakefood's format, for sfood-* tools
```

| Option | Meaning |
| --- | --- |
| `--dev` | Also scan tests: `test/` and `tests/` folders, `test_*.py`, `*_test.py`, `conftest.py`. Tests usually depend on everything, which hides the real structure. |
| `--source=PATH` | Add a folder, relative to the project, to the import roots (repeatable), for code importable from a folder the scanner does not find by itself. |
| `--venv=PATH` | Read installed packages from this virtualenv instead of the ones found in the project (repeatable). |
| `--format=json\|snakefood` | The pairs document (default) or snakefood's line format. |
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

`0` on success, `1` when the project folder does not exist or the output
cannot be written, `2` for a usage error. Warnings go to standard error and
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
