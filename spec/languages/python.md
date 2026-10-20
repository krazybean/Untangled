# Python profile

How the Python library turns a project into a [pairs document](../pairs-format.md).
It follows the approach of Martin Blais's
[snakefood](https://github.com/blais/snakefood): parse every file, collect its
imports, and resolve them against the project's import roots, without running
any of its code.

## Input

- The project root is the folder given on the command line. No manifest is
  required; `pyproject.toml` is read when present.
- **Scanned files** are the `.py` files under the root, except in:
  - hidden folders (name starting with `.`), `__pycache__`, `node_modules`,
    `site-packages`, `*.egg-info`, and any folder holding a `pyvenv.cfg`
    (a virtualenv);
  - `build/` and `dist/` at the project root.
- **Tests** are scanned only with `--dev` (tests usually depend on
  everything, which hides the real structure): files in a folder named `test`
  or `tests`, and files named `test_*.py`, `*_test.py` or `conftest.py`.
- A test file that a scanned file imports is scanned too, as PHP follows
  includes. (Django's `django/test/` package is real code, and stays in the
  graph as long as something imports it.)
- **Modules without Python source** are found too, but never scanned: stubs
  (`.pyi`), Cython sources (`.pyx`) and compiled extensions (`.so`, `.pyd`).
  They are import targets only (see [Module names](#module-names)).

## Import roots

An import is resolved against the **import roots**, the folders Python would
have on `sys.path`, in this order:

1. each `--source=<path>` (repeatable), a folder relative to the project root;
   a path that does not exist, is not a folder, or is outside the project is a
   warning;
2. from `pyproject.toml`, `[tool.setuptools] package-dir` for the `""` key,
   and each folder in `[tool.setuptools.packages.find] where`;
3. `src/`, when it exists and is not itself a package (has no `__init__.py`):
   the "src layout";
4. the project root.

The first root where a name resolves wins.

## Module names

A file's **module name** is its path relative to the import root that holds it,
using the root with the most path segments when several do: `src/shop/cart.py`
is `shop.cart` (root `src/`), `manage.py` is `manage`. The `.py` extension is
dropped, and `__init__.py` names its package (`shop/__init__.py` is `shop`).
A file whose path has a segment that is not a valid Python identifier (or is a
keyword), such as `scripts/my-tool.py`, has no module name.

A stub or an extension module has a module name the same way, with its
extension dropped; a compiled extension's name is the part before its first
dot (`_yaml.cpython-313-x86_64-linux-gnu.so` is `_yaml`). When a folder has
several files for one module, a `.py` file wins, then `.pyi`, `.pyx`, `.so`
and `.pyd`. An import of such a module is an edge to that file, an `internal`
node with no edges of its own.

The `module` of an internal node is its module name, when it has one, so
`--cluster=namespace:2` groups `shop.billing.invoice` into `shop.billing`.

A folder under a root that holds `.py` files but no `__init__.py` is a
**namespace package** (PEP 420). When a root has both `name.py` and
`name/__init__.py`, the package wins, as in Python.

## Resolving an import

`import a.b.c` and `__import__("a.b.c")` resolve the full dotted name:

1. **Project module.** A file whose module name, relative to any import root,
   is `a.b.c` (a module or a package's `__init__.py`). Every root is tried, so
   with both the project root and `src/` as roots, `src.shop.cart` and
   `shop.cart` both name `src/shop/cart.py`.
2. **Missing project module.** When `a` is a project module or regular package
   but `a.b.c` is not found, the target is `unresolved:module:a.b.c`. The
   scanner never points the edge at the nearest existing parent instead.
3. **Builtin.** When `a` is a standard library module, the target is
   `builtin:a`. The list is the running Python's `sys.stdlib_module_names`
   plus the modules removed from the standard library since Python 3.0 (such
   as `imp`, `distutils`, `asyncore` and the PEP 594 modules) and the ones
   added since Python 3.11 (such as `annotationlib`), so code is classified
   the same whichever Python runs the scanner.
4. **Package.** When the name belongs to an installed or declared
   distribution, the target is `pypi:<name>`, with the distribution name
   normalized as PyPI does (lowercase, runs of `-`, `_` and `.` written as
   `-`). See [Packages](#packages).
5. **Namespace package.** When `a.b.c` is a project namespace package, there is
   no file to point at and no edge is recorded (the submodules the code
   imports are resolved on their own), as PHP drops imports of namespaces.
6. Otherwise the target is `unresolved:module:a.b.c`.

Project modules come before builtins because a module at the top of an import
root shadows the standard library module of the same name, as it does when
Python runs the code. Builtins and packages come before namespace packages,
because Python prefers a regular package anywhere on `sys.path` over a
namespace package.

`from m import x` resolves `m.x` as a project module first (`from shop import
cart` imports `shop/cart.py`), then the module `m` (where `x` is a name defined
in `m`): when either is a project file, it is the target. Otherwise `m` is
resolved as above, and if `m` is a namespace package, `x` cannot be an
attribute of it, so the target is `unresolved:module:m.x`. `from m import *`
resolves `m`. Each imported name is one reference.

**Relative imports** (`from . import x`, `from ..m import x`) resolve from the
file's package: the module name itself for an `__init__.py`, else the module
name without its last segment. Each extra dot goes up one package. An import
that goes above the top-level package is `unresolved:module:<the import as
written>`: `..m` for `from ..m import x`, `..x` for `from .. import x`.

In a file without a module name, such as one in a package whose parent folder
is not an import root or not an identifier (`packages/my-plugin/my_plugin/`),
a relative import resolves from the file's folder instead, as Python does once
that package is importable: each extra dot goes up one folder, and every folder
it starts from or goes through must be a regular package (hold an
`__init__.py`); otherwise it is unresolved as written. `x` in `from .m import x`
is looked up as above: the submodule `m/x`, then the module `m`.

**Dynamic imports** are `importlib.import_module(...)`, `import_module(...)`
when imported from `importlib`, and `__import__(...)`. A string literal
argument is resolved like `import`; a relative literal is resolved against a
string literal `package` argument. Any other argument is
`unresolved:dynamic:<source text>`, the expression as written with runs of
whitespace collapsed to one space.

Not in v0.1: dotted strings in configuration (Django's `INSTALLED_APPS`,
entry points), `importlib.util.spec_from_file_location`, and `sys.path`
changes made at runtime.

## Packages

The scanner reads distributions from the project's virtualenvs: every folder
directly under the project root that holds a `pyvenv.cfg`, or the folders given
with `--venv=<path>` (repeatable, relative to the project root or absolute),
which replace them. In each, every `*.dist-info` folder under
`lib/python*/site-packages/` (or `Lib/site-packages/` on Windows) gives:

- the distribution name, from the `Name:` field of its `METADATA`;
- the modules it installs, from its `RECORD`: `yaml/__init__.py` installs
  `yaml`, `_yaml.cpython-313-x86_64-linux-gnu.so` installs `_yaml`, and every
  package level counts, so `google/auth/__init__.py` installs `google` and
  `google.auth`. A `*.egg-info` folder gives its modules through
  `top_level.txt` instead.

An import names the distribution that installs the longest prefix of its
dotted name: with `google-auth` and `google-cloud-storage` installed,
`google.auth.jwt` is `pypi:google-auth`. A prefix installed by more than one
distribution names none of them.

When no installed distribution matches, an import with a dotted prefix that
equals a **declared** dependency's name, after normalizing both, is that
dependency, the longest prefix first: `import typing_extensions` is
`pypi:typing-extensions`, and `import jaraco.abode.devices` is
`pypi:jaraco-abode` when `jaraco.abode` is declared (the usual naming of a
namespace package's distributions). Declared dependencies
are read from `pyproject.toml` (`[project] dependencies`,
`[project.optional-dependencies]`, `[dependency-groups]`, and Poetry's
`[tool.poetry.dependencies]`, `[tool.poetry.dev-dependencies]` and
`[tool.poetry.group.*.dependencies]`) and from `requirements*.txt` files at the
project root. Distributions whose import name differs from their name
(`import yaml` from `pyyaml`) can only be matched through a virtualenv; without
one they are unresolved, rather than guessed.

The scanner warns, without failing, when no virtualenv was found and imports
of modules that are not in the project are unresolved (naming the first few),
since they are likely third-party, and when a virtualenv has no
`site-packages`.

## Edge kinds

Each reference carries one kind for the statement, plus one for each context
it appears in. An edge's `kinds` is the union over its references.

| kind | meaning |
| --- | --- |
| `import` | `import a.b` |
| `from` | `from a import b` |
| `dynamic` | `importlib.import_module("a")`, `__import__("a")` |
| `relative` | a relative import (`from . import x`) |
| `local` | inside a function body |
| `type-checking` | inside `if TYPE_CHECKING:` (or `typing.TYPE_CHECKING`) |
| `conditional` | inside a `try` with a handler for `ImportError`, `ModuleNotFoundError`, `Exception` or everything (a bare `except:`), in the `try` body or such a handler |

## Encodings and Python 2

Files are decoded as Python does: a BOM or a PEP 263 coding comment
(`# -*- coding: latin-1 -*-`), else UTF-8. A file that is not valid in that
encoding is read as Windows-1252, as [pairs-format](../pairs-format.md)
requires for names, so legacy files still contribute their imports. File names
that are not valid UTF-8 are read the same way.

A file that does not parse as Python 3, such as Python 2 code
(`print "hello"`), is still a node, with `"error": "parse"`; the scanner warns
with the error and records no edges for it. A file that cannot be read gets
`"error": "read"`. A file that does not parse but is not Python 2 is read
statement by statement instead (see [Parser](#parser)).

## Parser

The reference implementation uses Python's own `ast` module, so the library
has no runtime dependencies. Python 3.11 or newer runs the scanner.

Code written for a newer Python than the one running the scanner (`type`
statements on 3.11, `except A, B:` on 3.13) does not parse as a whole. Such a
file is **read statement by statement**: it is split into logical lines with
the tokenizer, which changes far less between versions than the parser, and
nested by indentation. Each simple statement is parsed on its own, and so is
each block header with an empty body (for dynamic imports in a condition or a
default argument); a statement that still does not parse is skipped. An
import's contexts come from the blocks it is in: a `def` body is `local`, an
`if TYPE_CHECKING:` body is `type-checking`, and a `try` body or handler is
`conditional` under the same rule as above. For code that the running Python
does parse, this gives the same references as parsing the whole file.

A file is not read this way, and gives the parse error instead, when it cannot
be tokenized, or when a statement that does not parse uses syntax that only
Python 2 has: a `print` or `exec` statement, `raise E, "message"`, `<>`,
backticks, or a literal such as `0777` or `10L` (Python 2's implicit relative
imports mean something else in Python 3). The scanner warns once, naming the
first few files read this way, since imports inside the statements that did not
parse are missed.
