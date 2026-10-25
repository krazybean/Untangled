# Dependents

The `dependents` command answers "what depends on this file?" from a pairs
document, directly or through any chain of other files. It reads the
[pairs format](pairs-format.md) only, so it behaves the same for every
language.

```
untangled dependents [<path>|<pairs.json>] <target>... [--transitive]
                     [--include=<glob>]... [--exclude=<glob>]...
                     [--format=text|json] [--output=<file>]
```

A library also takes its scan options (`--dev`, `--source` and the like), for
when `<path>` is a project that has to be scanned first.

## Source

The first argument is the source when it is a folder or a file ending in
`.json`: a project to scan, or a saved pairs document. Anything else is a
target, and the source is the current folder. Pass `.` first to scan the
current folder when the first target is a `.json` file.

A document that contains `cluster` nodes is refused, as in
[metrics](metrics.md): ask about the file-level document.

## Targets

At least one target is required. Each is looked up in the document, in this
order:

1. A node id, of any kind: a file (`src/Billing/Tax.php`), or a package
   (`composer:acme/lib`), so "what uses this package?" works too.
2. A declared symbol: every internal node whose `symbols` list holds the
   target (`App\Billing\Tax`). The match is exact, and more than one file can
   declare the same symbol.

A target that matches nothing is an error (exit code 1); the command never
guesses. The dependents are those of all the targets together.

## What counts

An edge `from → to` makes `from` a **dependent** of `to`. Only internal nodes
can depend on anything, so dependents are always files of the project.

- **Direct** (the default): the files with an edge to a target. `depth` is 1.
- **`--transitive`**: also the files that depend on a dependent, and so on.
  `depth` is the shortest distance from any target: 1 for a direct dependent,
  2 for a dependent of a direct dependent. A file in a cycle is listed once,
  at its shortest depth.

A target is never listed as a dependent of itself or of another target, even
inside a cycle.

`--include` and `--exclude` use the globs of [clustering](clustering.md#filtering)
(the last matching pattern wins) and filter the **list**, not the walk: a file
is walked through even when a glob hides it, so a test that reaches a target
only through application code is still found by `--exclude=** --include=tests/**`.
Targets are looked up before filtering.

## Output

### JSON (`--format=json`)

```json
{
  "format": "untangled-dependents",
  "version": "0.1",
  "language": "php",
  "generator": { "name": "untangled-php", "version": "1.0.1" },
  "transitive": true,
  "targets": [
    { "target": "App\\Domain\\User", "nodes": ["src/Domain/User.php"] }
  ],
  "dependents": [
    { "id": "src/Domain/Order.php", "depth": 1 },
    { "id": "src/Http/UserController.php", "depth": 2 }
  ]
}
```

- `targets` has one entry per target, in the order given: the target as
  written and the sorted ids of the nodes it matched.
- `dependents` is sorted by `depth`, then by `id`. It is empty when nothing
  depends on the targets.
- Written like the other documents: two-space indentation, a trailing newline.

### Text (`--format=text`, the default)

For people: a count, then the dependents grouped by folder.

```
3 dependents of App\Domain\User

src/Domain/
  Order.php

src/Http/
  Router.php
  UserController.php
```

- The first line is `<n> dependents of <targets as written, joined by ", ">`
  (`1 dependent of`, `No dependents of` when there are none; nothing else is
  printed then).
- Each folder is a line ending in `/` (`./` for files at the root), sorted by
  folder; its files follow, indented by two spaces, sorted by name. A blank
  line separates the header and every folder.
- With `--transitive`, each file line ends with two spaces and `(depth <n>)`.

Sorting is by byte value, as everywhere in the spec.

## Exit codes

`0` when the query ran (even with no dependents), `1` when the source cannot
be read, or a target matches nothing, or the document is clustered, `2` for a
usage error (no target, an unknown option or format).
