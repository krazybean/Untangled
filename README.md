# Untangled

**Dependency health your whole team can understand.** Cycles, coupling and
trends over time, in the same terms for PHP, JavaScript/TypeScript and Python.

Untangled scans a codebase, builds the graph of which files depend on which,
and turns it into numbers and a readable report: where the cycles are, which
parts everything leans on, and which parts lean on everything. The reports are
written for engineers *and* for the people they report to, with plain-language
explanations of why coupling matters.

> **Status:** the PHP library (scanner, analyzer, HTML report, Graphviz
> export) is feature-complete for v1 but not released yet. Other languages
> follow; see [Roadmap](#roadmap).

## Credit: snakefood

Untangled is a re-imagining of **[snakefood](https://github.com/blais/snakefood)**
by **Martin Blais**. The idea and the design are his: scan source files into
a plain list of `(from, to)` dependency pairs, then filter, cluster and render
that list with small, composable tools. Untangled keeps that pipeline,

```
scan ──▶ pairs ──▶ filter / cluster ──▶ analyze ──▶ render
```

and its pairs format is a direct descendant of snakefood's (Untangled can
still write snakefood's format with `--format=snakefood`). snakefood supports
Python 2 only and has not been maintained since 2017; Untangled exists to carry
the idea to PHP first, then to JavaScript/TypeScript and Python 3, with metrics,
reports for non-engineers, and history over time added on top.

Thank you, Martin.

## Why Untangled

- **PHP first.** PHP has rule enforcement ([deptrac](https://github.com/deptrac/deptrac))
  but no maintained tool that visualizes dependencies and measures coupling.
- **Reports for the whole team.** One self-contained HTML report with an
  interactive graph and short explanations a manager can follow.
- **Change over time** (planned). Run against git history: "coupling in
  `Billing/` doubled this year", "this pull request added a cycle".
- **Comparable across languages.** Metric definitions live in one shared
  [specification](spec/README.md), and every language's library is tested
  against the same [conformance cases](conformance/README.md).

## Packages

One repository, one native library per language, with the same command name
and options everywhere. There are no cross-language edges: each language is
analyzed on its own.

| Language | Folder | Package | License | Status |
| --- | --- | --- | --- | --- |
| PHP | [`php/`](php/README.md) | `krazybean/untangled` (Composer) | MIT | v1 complete, not yet released |
| JavaScript / TypeScript | [`typescript/`](typescript/README.md) | `@krazybean/untangled` (npm) | MIT | Planned |
| Python | [`python/`](python/README.md) | `untangled` (PyPI) | GPL-2.0-only | scan, analyze and report work; not published yet |

## Quick start (PHP)

The PHP library needs a project with a `composer.json`: it resolves classes
through the project's Composer autoload rules.

```sh
cd php && composer install --no-dev
bin/untangled report /path/to/your/project --cluster=namespace:2 --output=report.html
```

Every command (`scan`, `analyze`, `report`) and option is documented in the
[PHP usage guide](php/README.md). `utg` is a short alias for `untangled`.

## Repository layout

| Folder | What it holds |
| --- | --- |
| [`spec/`](spec/README.md) | The language-neutral contract: pairs format, clustering, metric definitions, per-language profiles |
| [`conformance/`](conformance/README.md) | Fixture projects and the output every library must produce for them |
| [`php/`](php/README.md) | The PHP library and CLI |
| [`typescript/`](typescript/README.md) | The JavaScript/TypeScript library (planned) |
| [`python/`](python/README.md) | The Python library |
| [`docs/`](docs/README.md) | User documentation and design notes |

## Roadmap

**v1 (PHP):** scanner (Composer autoload → pairs), cycle detection, clustering
by namespace or folder, coupling metrics (fan-in, fan-out, instability
`I = Ce / (Ca + Ce)`), one readable HTML report with an interactive graph and
Graphviz DOT export.

**v2:** trends over git history.

**Python:** scan, analyze and report, checked on Django, Flask, pandas and
Home Assistant core.

**Next:** JavaScript/TypeScript, with its own scanner built on a real parser.
Importing dependency-cruiser output may come later as an `import` command.

## License

Untangled is split-licensed: `python/` is GPL-2.0-only because it may port
snakefood code, and everything else is MIT. The root [LICENSE](LICENSE)
explains the split, and each folder carries its own LICENSE file. See
[CONTRIBUTING](CONTRIBUTING.md) for what this means for contributions.
