# Dependents

The `dependents` command answers "what depends on this file?" from a pairs
document, directly or through any chain of other files. It reads the
[pairs format](pairs-format.md) only, so it behaves the same for every
language.

```
untangled dependents [<path>|<pairs.json>] <target>... [--transitive] [--max-depth=<n>]
                     [--through=<glob>]... [--include=<glob>]... [--exclude=<glob>]...
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

3. A spelling of a file path or of a symbol that is not an id but names
   one, tried only when 1 and 2 matched nothing, so a target that matched
   before still matches the same way:
   - **Paths.** Separators are written as `/`; repeated separators and `.` and
     `..` segments are collapsed (`.\src\Billing\Tax.php` is
     `src/Billing/Tax.php`). An **absolute** path (one that starts with `/`, or
     with a drive such as `C:/` or `C:\`) that is inside the project folder
     becomes its path relative to it; a drive letter matches in either case.
     The path and the folder are also compared with symbolic links resolved,
     so a pasted `pwd` works either way. The project folder is the source when
     it is a folder, else the current folder.
   - **Symbols.** A library may accept more spellings of its own language's
     symbols. The PHP library accepts a class name with a leading backslash
     (`\App\Billing\Tax` for `App\Billing\Tax`), see the
     [PHP profile](languages/php.md#dependents-targets).

A target that matches nothing is an error (exit code 1); the command never
guesses. An absolute path outside the project folder is an error too, which
says so, never a lookup under some other name. The dependents are those of all
the targets together.

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

Two kinds of options narrow the answer, and they work at different times:

- `--through` and `--max-depth` limit **the walk**.
- `--include` and `--exclude` filter **the list**, once the walk is done.

### Limiting the walk

**`--max-depth=<n>`** stops the walk after `n` steps from the targets: only
dependents with `depth` of at most `n` are found. `n` is a positive integer
written in decimal digits, without a sign or a leading zero; one larger than
the longest chain is the same as no limit. `--max-depth=1` finds the files
`--transitive` alone would list at depth 1, which are the direct dependents
(the document still says `"transitive": true`). It is a usage error (exit
code 2) without `--transitive`, rather than ignored: someone who asks for a
depth expects a walk that goes deeper than one step, and a depth of 1 is what
the command already does.

**`--through=<glob>`** (repeatable) limits the walk to some files. A file is
**eligible** when it matches at least one `--through` glob, using the globs of
[clustering](clustering.md#filtering); with no `--through`, every file is
eligible. The patterns are alternatives, there is no way to exclude with
`--through`, so no pattern takes precedence over another. The walk only goes
**into** eligible files:

- A file that is not eligible is never reached. It is not listed, not even
  when it uses a target directly (depth 1), and the walk does not go through it,
  so files that use the target only by way of an ineligible file are not found
  through that file. `depth` is the shortest distance over eligible files only.
- The targets are the start of the walk whatever they match, and so is every
  node a target names.
- It also applies without `--transitive`, where it keeps the direct dependents
  that are eligible.
- The check is made during the walk, one step at a time. Filtering the list
  afterwards would be different: a test reached only through application code
  is found by `--exclude=** --include=tests/**`, but not by
  `--through=tests/**`.

The two combine: `--through='src/**' --max-depth=2` is the application files
within two steps of the targets by way of application files only.

### Filtering the list

`--include` and `--exclude` use the globs of [clustering](clustering.md#filtering)
(the last matching pattern wins) and filter the **list**, not the walk: a file
is walked through even when a glob hides it, so a test that reaches a target
only through application code is still found by `--exclude=** --include=tests/**`.
Targets are looked up before filtering, and files that `--through` leaves out
are never in the list for them to filter.

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
be read, or a target matches nothing or is an absolute path outside the
project folder, or the document is clustered, `2` for a usage error (no
target, an unknown option or format, a `--max-depth` that is not a positive
integer or is given without `--transitive`):

```
Option --max-depth needs a positive integer, as in --max-depth=2 (got "0")
--max-depth only applies with --transitive
```
