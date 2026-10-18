# Conformance cases

Fixture projects that every Untangled library must produce the same documents
for. The [spec](../spec/README.md) says what the output means; these cases pin
it down.

```
cases/<case>/
├── README.md                  # what the case checks, in plain words
└── <language>/
    ├── project/               # the input project for that language
    └── expected/
        ├── pairs.json                 # the expected pairs document
        ├── analysis.json              # the expected analysis of the file graph
        ├── analysis.<strategy>.json   # optional: a clustered analysis
        └── graph[.<strategy>].dot     # optional: the report's DOT graph
    clusters.rules             # optional: the rules for analysis.rules.json
    sources                    # optional: --source paths for the scan, one per line
    aliases                    # optional: --aliases presets or files (relative to <language>/), one per line
```

`<strategy>` is the clustering with `:` written as `-`: `analysis.namespace-2.json`
is the analysis with `namespace:2`, `analysis.folder-1.json` with `folder:1`,
and `analysis.rules.json` with the rules in `clusters.rules`. Analyses use the
default filtering (builtins dropped, no path patterns).

A case can have a folder per language with the same logical shape (for
example, three files that depend on each other in a loop), so the libraries
can be compared on equal terms.

A library passes a case when its output equals the expected document after
ignoring the `generator` field, and its DOT graph (`untangled report
--format=dot`) equals `graph[.<strategy>].dot` byte for byte. Each library's test suite runs every case
that has a folder for its language.

## Cases

| Case | Checks |
| --- | --- |
| [psr4-basic](cases/psr4-basic/README.md) | Class-reference kinds, builtins, unresolved classes |
| [three-cycle](cases/three-cycle/README.md) | A dependency loop and a file with no dependencies |
| [includes](cases/includes/README.md) | `classmap` / `files` autoload, followed and unresolved includes, functions and constants |
| [composer-packages](cases/composer-packages/README.md) | Packages from `composer.lock`, psr-0 prefixes, imports of namespaces |
| [vendor-installed](cases/vendor-installed/README.md) | Packages from `vendor/`, classmap packages, includes into `vendor/` |
| [legacy-app](cases/legacy-app/README.md) | Code outside autoload added with `--source`, includes found through `--source` folders, a Latin-1 class name, a polyfill that a builtin wins over, Composer's autoloader and runtime classes |
| [class-aliases](cases/class-aliases/README.md) | Global class aliases from `--aliases`: a preset, aliases packages declare, a file that overrides the preset, and names nobody declares |
| [layers](cases/layers/README.md) | Clustering by namespace, folder and rules; Ca / Ce; a cycle between clusters that no file cycle shows, and a file cycle that disappears inside a cluster |
| [python-packages](cases/python-packages/README.md) | Python: submodules versus names in `from` imports, namespace packages, a package shadowing a module, a missing module in a project package |
| [relative-imports](cases/relative-imports/README.md) | Python: relative imports, including above the top-level package and from a top-level module |
| [src-layout](cases/src-layout/README.md) | Python: import roots from `src/`, `pyproject.toml` and `--source` |
| [stdlib-and-packages](cases/stdlib-and-packages/README.md) | Python: builtins, distributions from a virtualenv's `RECORD` files, declared dependencies, a module shadowing the standard library |
| [import-kinds](cases/import-kinds/README.md) | Python: `TYPE_CHECKING`, `try`/`except ImportError`, local and dynamic imports |
| [legacy-python](cases/legacy-python/README.md) | Python: a Python 2 file, Latin-1 and Windows-1252 files, test folders and a test module real code imports |

## Adding a case

1. Create `cases/<case>/README.md` and `cases/<case>/<language>/project/`.
2. Generate the expected output with the library, e.g.
   `php/bin/untangled scan conformance/cases/<case>/php/project --output=conformance/cases/<case>/php/expected/pairs.json`
   and `php/bin/untangled analyze conformance/cases/<case>/php/project --output=conformance/cases/<case>/php/expected/analysis.json`
   (add `--cluster=namespace:2` and so on for a clustered analysis).
   For Python, with the library installed (`pip install -e python`):
   `untangled scan conformance/cases/<case>/python/project --output=conformance/cases/<case>/python/expected/pairs.json`,
   adding `--source=...` for each line of `python/sources`. Until the Python library has `analyze` and `report`, its
   expected analyses and DOT graphs are made by the PHP library from that
   pairs document (`php/bin/untangled analyze .../python/expected/pairs.json`),
   which works because both read the same format.
3. **Read the expected output line by line** and check it against the spec
   before committing. Generated output is only a starting point.
