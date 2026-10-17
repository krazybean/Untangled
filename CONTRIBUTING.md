# Contributing

Thanks for helping untangle things. A few rules keep the project coherent
across languages and keep its licensing clean.

## Licensing of contributions

**A contribution takes the license of the folder it lands in.** By opening a
pull request you agree that your changes to `php/`, `typescript/`, `spec/`,
`conformance/`, `docs/` or root-level files are licensed under the MIT
license, and your changes to `python/` under the GNU GPL version 2 only. See
[LICENSE](LICENSE) for the full map.

- Code ported or translated from [snakefood](https://github.com/blais/snakefood)
  (GPL), even from Python 2 to Python 3, is a derivative work. It may only go
  into `python/`.
- GPL-licensed code must never be copied into an MIT folder. Reusing ideas,
  the pairs format and concepts defined in `spec/` is fine anywhere.
- Do not copy code from projects without a license (for example
  trim21/snakefood3): no license means no permission.
- Every source file starts with an SPDX header for its folder's license, e.g.
  `// SPDX-License-Identifier: MIT` or `# SPDX-License-Identifier: GPL-2.0-only`.
  `scripts/check-licenses.sh` enforces this in CI.

## Each language owns its dependencies

Every language folder is a self-contained project in its ecosystem's standard
layout, and the repository root has no package manifest, lockfile or build
tool of its own:

| Folder | Manifest | Tooling | Ignores |
| --- | --- | --- | --- |
| `php/` | `composer.json` | Composer (`composer test`) | `php/.gitignore` |
| `typescript/` | `package.json` | npm | `typescript/.gitignore` |
| `python/` | `pyproject.toml` | pip / a PEP 517 backend | `python/.gitignore` |

- Add a dependency to the folder that uses it, with that ecosystem's tool,
  run from inside the folder (`composer require`, `npm install`, ...).
- Never add a root-level `composer.json`, `package.json`, `pyproject.toml`,
  workspace file or shared script that installs or runs another language's
  dependencies. Libraries share only the [spec](spec/README.md) and the
  [conformance cases](conformance/README.md), never code or packages.
- Lockfiles follow each ecosystem's convention for a library.
- Each language has its own CI workflow (`.github/workflows/<language>.yml`)
  that runs inside its folder, and its own Dependabot entry.
- Root-level files are limited to repository concerns: the license map and
  texts, README, CONTRIBUTING, and `scripts/check-licenses.sh`.

## Spec first

The [specification](spec/README.md) is authoritative; no language's code is.
When a change alters observable output (the pairs document, a metric, a
report number), change the spec first and add or update a
[conformance case](conformance/README.md) in the same pull request.

## Checks

From the repository root:

```sh
scripts/check-licenses.sh

# PHP 8.2+, from inside php/
cd php
composer install
composer validate --no-check-publish --strict
composer test
```
