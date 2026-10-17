# Metrics

Metrics are computed on a pairs document after filtering and, optionally,
clustering. A **unit** is an internal node of that document: a file, or a
cluster if the graph was clustered. Only edges between two units count toward
coupling and cycles; edges to `external` and `unresolved` nodes are reported
separately.

Each metric below has a plain-language line. Reports MUST use that wording (or a
translation of it) so every language's report explains metrics the same way.

## Per unit

Let `G` be the graph of units and `u → v` mean "`u` depends on `v`".

| metric | definition | plain language |
| --- | --- | --- |
| `fan_out` | number of distinct units `v ≠ u` with `u → v` | "How many other parts of the code this one relies on." |
| `fan_in` | number of distinct units `v ≠ u` with `v → u` | "How many other parts of the code rely on this one." |
| `external` | number of distinct `external` nodes `u` depends on | "How many third-party packages this part uses directly." |
| `unresolved` | number of distinct `unresolved` nodes `u` depends on | "References we could not trace; the real coupling may be higher." |
| `instability` | `fan_out / (fan_in + fan_out)`, or `null` when both are 0 (on a cluster graph, `ce / (ca + ce)`, see below) | See below. |

On a cluster graph, `fan_in` and `fan_out` count clusters, and `external` and
`unresolved` count the distinct nodes that any file of the cluster depends on.

**Instability** (Robert C. Martin's `I = Ce / (Ca + Ce)`) is a number from 0
to 1. At 0, many parts depend on this one and it depends on nothing: changing
it is risky, so it tends not to change ("stable"). At 1, it depends on others
and nothing depends on it: easy to change, but it breaks when they change
("unstable"). Plain language: *"How much this part is pushed around by changes
elsewhere, from 0 (others lean on it) to 1 (it leans on others)."* A unit with
no internal dependencies in either direction has `null` instability, not 0.

## Per cluster: Ca and Ce

When the graph is clustered, `Ca` (afferent coupling) and `Ce` (efferent
coupling) are also reported for each cluster `C`, counted in **files**:

- `Ce(C)` = number of distinct internal files outside `C` that files in `C` depend on.
- `Ca(C)` = number of distinct internal files outside `C` that depend on files in `C`.
- `instability(C) = Ce / (Ca + Ce)`, `null` when both are 0. This is the value
  written in a cluster unit's `instability` field, in place of the fan-based
  formula, as in Robert C. Martin's package metrics.

Ca and Ce are computed on the filtered file graph, before edges inside a
cluster are dropped; edges between two files of the same cluster never count.

Counting files rather than clusters means one cluster leaning heavily on
another scores higher than one touching it once. For a cluster of exactly one
file, `Ca = fan_in` and `Ce = fan_out`.

> Note: JDepend and some other tools define `Ce` as the number of classes
> *inside* the package that have outside dependencies. Untangled counts the
> outside targets so that `Ca` and `Ce` are symmetric. This is a deliberate
> choice; reports must not compare these numbers with other tools as equal.

## Cycles

A **cycle** is a set of units that all (directly or indirectly) depend on each
other: a strongly connected component of `G` with two or more units.
Plain language: *"These parts all depend on each other, so none of them can be
changed, tested or reused alone."*

For each cycle the analysis reports:

- `members`: the units in it, sorted;
- `size`: the number of members;
- `example`: one concrete loop, for explaining it in a report. It is the
  shortest path from the smallest member (byte order) back to itself, found by
  breadth-first search visiting neighbours in byte order, written as a list
  that starts and ends with that member. Among loops of the same length, the
  first one that search reaches wins: for `a → b`, `a → c`, `b → a`, `c → a`
  the example is `[a, b, a]`.

Cycles are sorted by size (largest first), then by their first member.

## Project summary

| field | definition |
| --- | --- |
| `units` | number of units |
| `edges` | number of unit-to-unit edges |
| `cycles` | number of cycles |
| `largest_cycle` | size of the largest cycle, 0 if none |
| `units_in_cycles` | number of units that are in some cycle |
| `units_in_cycles_ratio` | `units_in_cycles / units`, 0 if there are no units |
| `mean_fan_out` | mean `fan_out` across units, 0 if there are no units |
| `external_packages` | number of distinct external nodes used by any unit |
| `unresolved_references` | number of distinct unresolved nodes |

Candidates for later versions (not in v0.1): propagation cost, depth of the
dependency tree, distance from the main sequence (`|A + I − 1|`, needs an
abstractness measure per language).

## The analysis document

```json
{
  "format": "untangled-analysis",
  "version": "0.1",
  "language": "php",
  "generator": { "name": "untangled-php", "version": "0.1.0" },
  "clustering": "namespace:2",
  "summary": { "units": 2, "edges": 1, "cycles": 0, "largest_cycle": 0,
               "units_in_cycles": 0, "units_in_cycles_ratio": 0,
               "mean_fan_out": 0.5, "external_packages": 1,
               "unresolved_references": 1 },
  "units": [
    { "id": "src/Billing/Invoice.php", "fan_in": 0, "fan_out": 1,
      "external": 1, "unresolved": 0, "instability": 1 },
    { "id": "src/Billing/Tax.php", "fan_in": 1, "fan_out": 0,
      "external": 0, "unresolved": 1, "instability": 0 }
  ],
  "cycles": []
}
```

`clustering` is `null` for a file graph, otherwise the strategy as written in
[clustering](clustering.md): `namespace:N`, `folder:N` or `rules` (never the
path of the rules file). `units` is sorted by `id`.

Cluster units additionally carry `ca`, `ce` and `members` (the sorted internal
ids in the cluster), in this key order:

```json
{ "id": "App\\Domain", "fan_in": 2, "fan_out": 1, "ca": 2, "ce": 1,
  "external": 0, "unresolved": 0, "instability": 0.3333,
  "members": ["src/Domain/Order.php", "src/Domain/User.php"] }
```

Fractions are rounded to at most 4 decimal places; whole numbers (including
`0` and `1`) are written without a decimal point.
