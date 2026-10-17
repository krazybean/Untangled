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
| [layers](cases/layers/README.md) | Clustering by namespace, folder and rules; Ca / Ce; a cycle between clusters that no file cycle shows, and a file cycle that disappears inside a cluster |

## Adding a case

1. Create `cases/<case>/README.md` and `cases/<case>/<language>/project/`.
2. Generate the expected output with the library, e.g.
   `php/bin/untangled scan conformance/cases/<case>/php/project --output=conformance/cases/<case>/php/expected/pairs.json`
   and `php/bin/untangled analyze conformance/cases/<case>/php/project --output=conformance/cases/<case>/php/expected/analysis.json`
   (add `--cluster=namespace:2` and so on for a clustered analysis).
3. **Read the expected output line by line** and check it against the spec
   before committing. Generated output is only a starting point.
