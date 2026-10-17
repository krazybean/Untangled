# Clustering and filtering

Both steps turn one pairs document into another pairs document, so they can be
chained and every later step (metrics, reports) works on either a file graph or
a cluster graph.

## Filtering

Applied before clustering, in this order:

1. **Kind filter.** By default `builtin` nodes and their edges are removed.
   `external` and `unresolved` nodes are kept (reports list them) but are
   excluded from metrics, see [metrics](metrics.md).
2. **Path filter.** Ordered `include` / `exclude` glob patterns on internal ids.
   `*` matches any characters except `/`, `?` one character except `/`, and
   `**` any characters including `/`; `**/` also matches no directory at all,
   so `**/Test*.php` matches `TestA.php`. A pattern matches the whole id. The
   last matching pattern wins; a file matching no pattern is included.
   Removing a node removes its edges.

After both filters, an `external` or `unresolved` node that no remaining edge
points to is removed too, so reports and the summary only list what the
remaining files use.

## Clustering

Clustering maps every internal node to a **cluster id**. A strategy is one of:

| strategy | cluster id of an internal node |
| --- | --- |
| `namespace:N` | The first `N` segments of its `module` (`App\Billing\Tax` with N=2 → `App\Billing`). A node with no `module` falls back to `folder:N`. |
| `folder:N` | The first `N` directory segments of its id (`src/Billing/Tax.php` with N=2 → `src/Billing`). A file with fewer directories keeps its full directory path; a file at the root goes to `.`. |
| `rules` | An ordered list of `prefix → cluster` rules on the node id; the first matching prefix wins; an unmatched node keeps its own id (it is its own cluster). This mirrors snakefood's `sfood-cluster`. |

Non-internal nodes are never clustered; they pass through unchanged.

The output document:

- has one node per cluster with `"kind": "cluster"` and a sorted `members`
  list of the internal ids it contains (`{ "id": "App\\Billing", "kind":
  "cluster", "members": ["src/Billing/Invoice.php", "src/Billing/Tax.php"] }`);
- has one edge per `(cluster, target)` pair, where `count` is the sum and
  `kinds` the union of the merged edges;
- drops edges whose `from` and `to` fall in the same cluster (they are
  internal to it), but reports SHOULD show how many were dropped per cluster.

Metrics are always computed from the file-level document plus a strategy, not
from an already clustered document, because Ca and Ce count files (see
[metrics](metrics.md)). Libraries MUST refuse to analyze a document that
contains `cluster` nodes.

A rules file looks like this: one rule per line, a prefix and a cluster name
separated by whitespace (neither may contain whitespace), `#` starts a comment.
A line with any other number of fields is an error.

```
# prefix              cluster
src/Billing/          Billing
src/Invoice           Billing
src/                  Core
```
