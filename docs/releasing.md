# Releasing

Each language is versioned and released on its own, from a tag in this
repository with the language as a prefix: `php/v1.0.0`, `python/v1.0.0`,
`typescript/v1.0.0`. Versions follow semantic versioning; the pairs
document, the analysis document and the command-line options are the public
interface, so a breaking change to any of them is a major version.

## Before any release

- The repository should be public. The PyPI and Packagist pages link to the
  usage guides, examples and changelog here, and those links only work for
  readers who can open this repository.
- CI is green on `main`.

## Python (PyPI: `untangled`)

**Once:** on [pypi.org](https://pypi.org/manage/account/publishing/) and on
[test.pypi.org](https://test.pypi.org/manage/account/publishing/), add a
pending trusted publisher for the project `untangled` with owner
`krazybean`, repository `Untangled`, workflow `python-release.yml`, and
environment `pypi` (on TestPyPI: `testpypi`). Then create both environments
under the repository's Settings → Environments. No token is stored anywhere:
the workflow proves who it is to PyPI with GitHub's OIDC token.

**Each release:**

1. Set the version in `python/src/untangled/version.py` and add its entry to
   `python/CHANGELOG.md`, in a PR.
2. After it merges, tag `main` and push the tag:
   `git tag python/v1.0.0 && git push origin python/v1.0.0`.
3. [`python-release.yml`](../.github/workflows/python-release.yml) checks the
   tag against `version.py`, builds the sdist and wheel, runs the test suite
   against the installed wheel, and uploads to PyPI.

A pre-release tag such as `python/v1.1.0rc1` (with `version.py` set to
`1.1.0rc1`) goes to TestPyPI instead, for a dry run:
`pip install -i https://test.pypi.org/simple/ untangled==1.1.0rc1`.

## PHP (Packagist: `krazybean/untangled`)

Packagist needs `composer.json` at the root of a repository, so the package
is published from a second repository, `krazybean/krazybean-untangled-php`,
which holds nothing but the exported package. This is the same setup as
Conduit and `krazybean/krazybean-conduit-php`.

**Once:**

1. Create the public, empty repository `krazybean/krazybean-untangled-php`.
2. Create a fine-grained personal access token (or a GitHub App) with
   **Contents: Read and write** on that repository only, and add it to this
   repository as the Actions secret `UNTANGLED_PHP_DISTRIBUTION_TOKEN`.
3. Run the **PHP distribution** workflow by hand (Actions → PHP distribution
   → Run workflow, on `main`). It pushes the current package to the export
   repository's `main`, without a tag.
4. Submit `https://github.com/krazybean/krazybean-untangled-php` on
   [packagist.org](https://packagist.org/packages/submit), and check that
   Packagist's GitHub hook is on, so new tags appear by themselves.

**Each release:**

1. Set `VERSION` in `php/src/Version.php` and add its entry to
   `php/CHANGELOG.md`, in a PR.
2. After it merges: `git tag php/v1.0.0 && git push origin php/v1.0.0`.
3. [`php-distribution.yml`](../.github/workflows/php-distribution.yml) runs
   the test suite, exports `php/` with
   [`scripts/export-php.sh`](../scripts/export-php.sh), installs the export
   in an empty Composer project and runs it, then pushes it to the export
   repository as one commit with the annotated tag `v1.0.0`. Packagist reads
   the tag from there.

The export holds `composer.json` (without the test setup), `README.md`,
`CHANGELOG.md`, `LICENSE`, `bin/`, `src/` and `resources/`. Tests stay here,
next to the conformance cases they read.

## JavaScript / TypeScript (npm: `@krazybean/untangled`)

Published from the maintainer's machine with `npm publish`, the same way as
other `@krazybean` packages: the account has two-factor authentication for
publishing, so npm asks for the security key, and no token is stored in this
repository. `publishConfig` in `typescript/package.json` makes the scoped
package public.

**Each release:**

1. Set the version in `typescript/package.json` and `typescript/src/version.ts`
   (a test checks they match) and add its entry to `typescript/CHANGELOG.md`,
   in a PR. CI packs the package and runs the packed CLI, so a file missing
   from the package fails there.
2. After it merges, publish from a clean checkout of `main` and tag it:

   ```sh
   git switch main && git pull
   cd typescript && npm ci
   npm publish                  # runs typecheck and tests first; asks for 2FA
   git tag typescript/v1.0.0 && git push origin typescript/v1.0.0
   ```

`npm publish --dry-run` shows the files that would go up. A pre-release
(`1.1.0-rc.1`) is published with `npm publish --tag next`, so `npm install`
keeps getting the latest stable version.

Publishing from CI instead would use npm trusted publishing: add the workflow
as a trusted publisher in the package's settings on npmjs.com (possible once
the package exists), and the workflow publishes with provenance and no token.

## GitHub Release

After any of the releases above, publish a GitHub Release for the tag
(Releases → Draft a new release → choose the tag), titled after the library
and version, such as **PHP 1.0.0**, with that version's changelog entry as
the notes. Leave **Set as the latest release** on for the newest one. The
release is what watchers of the repository are notified about, and where
readers look for what changed.
