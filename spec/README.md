# Untangled specification: draft v0.1

This language-neutral contract is authoritative. Every Untangled library (PHP
first, then TypeScript and Python) must produce equivalent documents for the
same input. A library's API may be idiomatic for its language; its output may
not differ. MUST / SHOULD / MAY are used in the RFC 2119 sense.

Untangled follows the pipeline of Martin Blais's
[snakefood](https://github.com/blais/snakefood):

```
scan ──▶ pairs ──▶ filter / cluster ──▶ analyze ──▶ render
```

| Document | Contract |
| --- | --- |
| [Pairs format](pairs-format.md) | Nodes, edges, external and unresolved targets, the JSON document |
| [Clustering and filtering](clustering.md) | Grouping files into namespaces or folders, aggregating edges |
| [Metrics](metrics.md) | Fan-in, fan-out, Ca, Ce, instability, cycles, project summary |
| [Reports](report.md) | The `report` command: what the HTML report shows, and the Graphviz DOT graph |
| [PHP profile](languages/php.md) | What the PHP scanner reads and how it resolves references |
| [Python profile](languages/python.md) | What the Python scanner reads and how it resolves imports |

Later: `languages/typescript.md`, and a trends document
for v2 (metrics over git history).

## Principles

1. **One graph per language.** There are no cross-language edges.
2. **Files are nodes.** Every library builds a file-level graph first; namespaces,
   folders and packages are clusters on top of it. This keeps metrics comparable
   across languages, as in snakefood.
3. **Never guess silently.** A reference that cannot be resolved becomes an
   `unresolved` node, never a dropped edge and never a fabricated one.
4. **Deterministic output.** Same input, same bytes: documents are sorted as
   specified so they can be diffed and checked into conformance fixtures.
5. **Plain-language definitions.** Each metric has a one-sentence explanation a
   non-engineer can read; reports reuse these sentences verbatim.

## Versioning

Every document carries `"version"`. While the spec is `0.x`, minor versions
may break. Libraries MUST reject a document with a major version they do not
know, and SHOULD warn on an unknown minor version.

## Conformance

`conformance/cases/<case>/<language>/project/` holds an input project and
`conformance/cases/<case>/<language>/expected/` the documents a library must
produce for it: `pairs.json` for the scan, `analysis.json` for the analysis of
the file graph with default filtering, and `analysis.<strategy>.json` for a
clustered analysis, where `<strategy>` is the clustering with `:` written as
`-` (`analysis.namespace-2.json`), or `rules` with the rules in
`<language>/clusters.rules`. A case whose project needs `--source` paths
lists them, one per line, in `<language>/sources`. A library passes a case when its output equals
the expected document after ignoring the `generator` field and comparing
numbers to 4 decimal places. A case may also pin the [DOT graph](report.md#dot-graph)
in `graph.dot` (file graph) and `graph.<strategy>.dot`, compared byte for byte.
