# Pairs format

A scan produces a **pairs document**: the set of `(from, to)` dependency pairs
between files of one project, in one language. It is the hand-off point between
scanning and everything after it, so other tools can produce or consume it.

## Nodes

A node is identified by a string `id`. There are four kinds:

| kind | id form | example | meaning |
| --- | --- | --- | --- |
| `internal` | project-relative POSIX path | `src/Billing/Invoice.php` | A source file of the project. Followed. |
| `external` | `<ecosystem>:<package>` | `composer:monolog/monolog`, `pypi:requests`, `npm:lodash` | A third-party package. Not followed. |
| `builtin` | `builtin:<name>` | `builtin:DateTimeImmutable` | Part of the language or runtime. Not followed. |
| `unresolved` | `unresolved:<what>:<text>` | `unresolved:class:App\Legacy\Foo` | A reference the scanner could not resolve. |

A clustered document (see [clustering](clustering.md)) replaces internal nodes
with a fifth kind, `cluster`, whose nodes carry the `members` they group.

Rules:

- Internal ids MUST be relative to the project root, use `/` separators, have
  no leading `./`, and keep the file extension.
- Every scanned internal file MUST appear as a node, even when it has no edges
  (snakefood writes these as `(file, None)`).
- An internal node MAY carry `module` (its namespace or package, used by
  clustering) and `symbols` (the names it declares, sorted).
- An internal node MUST carry `error` when the scanner could not take any
  references from the file: `"parse"` when it does not parse, `"read"` when it
  cannot be read at all. Such a file's dependencies are unknown, not absent,
  so [reports](report.md) MUST say which files could not be read. A file read
  only in part (the language profile says when) has no `error`. The value is
  one of these words, never the parser's message, so documents stay the same
  whatever parser version produced them. `error` comes after the node's other
  fields.
- External nodes are per package, not per class or file inside the package.
- `<what>` in unresolved ids is defined by the language profile (for PHP:
  `class`, `function`, `include`; for Python: `module`, `dynamic`).

## Edges

An edge says "`from` depends on `to`". `from` is always an internal node.

| field | type | meaning |
| --- | --- | --- |
| `from` | node id | The depending file |
| `to` | node id | The file, package or name it depends on |
| `kinds` | sorted list of strings | Why: how the dependency appears in the code (`import`, `extends`, `new`, ...). Vocabulary is set by the language profile. |
| `count` | integer ≥ 1 | Number of references found. For display and weighting; metrics ignore it. |

Rules:

- There is at most one edge per `(from, to)` pair; repeated references merge
  their `kinds` and add to `count`.
- Self-edges (a file depending on itself) MUST be dropped.
- Edges to `external`, `builtin` and `unresolved` nodes MUST be recorded, so
  reports can show them, but those nodes are never scanned.

## The document

```json
{
  "format": "untangled-pairs",
  "version": "0.1",
  "language": "php",
  "generator": { "name": "untangled-php", "version": "0.1.0" },
  "nodes": [
    { "id": "builtin:DateTimeImmutable", "kind": "builtin" },
    { "id": "composer:monolog/monolog", "kind": "external" },
    { "id": "src/Billing/Invoice.php", "kind": "internal",
      "module": "App\\Billing", "symbols": ["App\\Billing\\Invoice"] },
    { "id": "src/Billing/Tax.php", "kind": "internal",
      "module": "App\\Billing", "symbols": ["App\\Billing\\Tax"] },
    { "id": "src/legacy/broken.php", "kind": "internal", "error": "parse" },
    { "id": "unresolved:include:$base . '/legacy.php'", "kind": "unresolved" }
  ],
  "edges": [
    { "from": "src/Billing/Invoice.php", "to": "builtin:DateTimeImmutable",
      "kinds": ["new"], "count": 1 },
    { "from": "src/Billing/Invoice.php", "to": "composer:monolog/monolog",
      "kinds": ["import", "type"], "count": 2 },
    { "from": "src/Billing/Invoice.php", "to": "src/Billing/Tax.php",
      "kinds": ["import", "static"], "count": 3 },
    { "from": "src/Billing/Tax.php", "to": "unresolved:include:$base . '/legacy.php'",
      "kinds": ["include"], "count": 1 }
  ]
}
```

- `nodes` MUST be sorted by `id`; `edges` by `from`, then `to` (plain byte order).
- Absolute paths MUST NOT appear anywhere in the document, so documents are
  portable and safe to share.
- Documents are UTF-8. A name or path read from source code or the filesystem
  that is not valid UTF-8 (legacy code saved as Latin-1 can declare
  `class Café`) MUST be read as Windows-1252 and written as the equivalent
  UTF-8, so it stays distinct and readable rather than replaced or rejected.
- Writers SHOULD emit two-space indentation and a trailing newline.

## snakefood interop

Libraries SHOULD offer `--format=snakefood`, which writes one Python tuple per
line, `((root, from), (root, to))`, with `((root, file), (None, None))` for
files without internal dependencies. `root` is the project path as given on
the command line, and lines are sorted. Only internal-to-internal edges and dependency-free
files are written, since snakefood has no notion of external or unresolved
nodes. This lets existing snakefood-format tooling (and spin-offs such as
crowfood) read Untangled output.
