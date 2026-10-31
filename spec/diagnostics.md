# Diagnostics

Untangled tells you about problems that did not stop a command (a file it could
not parse, files it did not scan, a rules file that leaves files out) and about
the one that did. These are **diagnostics**. They are written to standard
error, never to standard output: stdout holds only the command's result (a
pairs document, an analysis, a report, a list of dependents), so a diagnostic
cannot corrupt data that is piped or saved.

By default a diagnostic is a line of text. With `--diagnostics=json` it is a
JSON object, one per line, that a program can read without looking at the
wording of the message.

```
untangled scan <path> [--diagnostics=text|json]
```

`--diagnostics` is accepted by every command (`scan`, `analyze`, `report`,
`dependents`). A command that has nothing to say writes nothing to standard
error in either mode.

## Formats

| `--diagnostics=` | Standard error |
| --- | --- |
| `text` (the default) | One line per diagnostic: `warning: <message>` or `error: <message>`. |
| `json` | One JSON object per line ([JSON Lines](https://jsonlines.org/)), described below. |

Any other value is a usage error (exit code 2), like an unknown `--format`:

```
Unknown diagnostics format: github (use text or json)
```

`--diagnostics=github`, annotations for GitHub Actions, is **not supported yet**.
It is meant to be a separate output that reads this one; nothing in the model
below knows about any CI system.

Usage errors (exit code 2: an unknown option or command, a missing value)
describe how to call the command, not what is wrong with a project. They are
not diagnostics: they are written as text, with the usage summary where there
was one, in both modes.

## The diagnostic object

```json
{"level":"warning","code":"uncovered-files","message":"3 PHP files are not covered by composer.json autoload rules and were not scanned (routes/ 2, bootstrap/ 1); add folders with --source=<folder> if they hold code you want analyzed","files":["bootstrap/app.php","routes/api.php","routes/web.php"]}
```

| Field | Type | |
| --- | --- | --- |
| `level` | string | `warning` or `error`. A new level is a new version of this specification. |
| `code` | string | Names the condition, in lower case with hyphens (`file-unparseable`). Stable: a code is never reused for another condition, and the same condition has the same code in every library. The variable details of one occurrence are in `message` and `files`, never in the code. |
| `message` | string | The sentence for people, the same as the text mode writes after `warning: ` or `error: `. It is English, may change between versions, and may differ in wording between libraries. Programs must not read it. |
| `files` | array of strings | Optional. The project-relative paths the diagnostic is about, with `/` as separator: files, or folders when the condition is about a folder (`build-output-skipped`). Absent when no path is relevant. Never empty. |

The fields are written in this order, and no others are written. A reader
should ignore a field it does not know, because later versions may add some.

**There is no source location yet.** The libraries do not all know a line or
column in a reliable, structured way (a parse error's position is a part of the
message in some and absent in others), and a made-up location is worse than
none. A later version may add optional `line` and `column` fields to the codes
that can fill them.

### Level

- `warning`: the command went on and produced its result. The exit code is not
  changed.
- `error`: the command stopped, or, with `--strict`, was made to stop. It is
  the last diagnostic of the run and the exit code is 1. A command ends with at
  most one error.

### Order, and duplicates

Diagnostics are written in the order the library produced them, which is the
order of the text lines, and that order is deterministic: the same project and
options give the same lines. Scan diagnostics come before the diagnostics of
the steps after it (clustering, analysis).

Occurrences are not merged by the writer: two files that fail to parse are two
diagnostics, each with its own `files`. A condition that is one fact about many
files is one diagnostic that lists them, and the libraries keep it that way
(`uncovered-files` is one diagnostic with every uncovered file, sorted, not one
per file).

### JSON Lines encoding

Each line is one JSON object, written without spaces between tokens, in UTF-8,
ending with `\n`. A diagnostic is never split over several lines: line breaks,
quotes, backslashes and the other control characters (U+0000 to U+001F) inside
a string are escaped as JSON requires, using `\n`, `\r`, `\t`, `\b`, `\f`,
`\"` and `\\`, and `\u00XX` with lower-case hex digits for the rest. `/` and
characters outside ASCII are written as they are. Text that is not valid UTF-8,
such as a file name in another encoding, is written with U+FFFD in its place.

## Codes

Not every library can meet every condition, so a library writes the codes that
apply to it. A condition that exists in more than one library has one code.

### Warnings

| Code | When | `files` | Libraries |
| --- | --- | --- | --- |
| `source-not-found` | A `--source` path names nothing in the project. | The path. | all |
| `source-outside-project` | A `--source` path is outside the project and was ignored. | | Python, TypeScript |
| `file-unparseable` | A file could not be parsed. It stays in the pairs document with `"error": "parse"`. | The file. | all |
| `file-unreadable` | A file could not be read. It stays in the pairs document with `"error": "read"`. | The file. | Python, TypeScript |
| `file-partially-parsed` | Some files did not parse whole, and the imports the library could still read were kept. One diagnostic for all of them. | The files. | Python, TypeScript |
| `nothing-scanned` | There was no file to scan. | | all |
| `config-unreadable` | A configuration file of the project (`pyproject.toml`, `package.json`, `tsconfig.json`) could not be read and was ignored. | The file. | Python, TypeScript |
| `aliases-ignored` | A file given with `--aliases` is missing, unreadable or not a JSON object of aliases, and was ignored. | | TypeScript |
| `venv-not-found` | A `--venv` path is not a folder. | The path. | Python |
| `venv-without-site-packages` | A virtualenv has no `site-packages` folder, so its packages are not read. | The virtualenv. | Python |
| `package-list-missing` | The installed packages could not be listed because they are not installed (no `vendor/composer/installed.json` and no `composer.lock`; no virtualenv; no `node_modules`), so third-party imports show as unresolved. | | all |
| `package-list-unreadable` | The package list exists but is not readable. | | PHP |
| `uncovered-files` | PHP files under the project are not covered by any `autoload` rule, `--source` path or include, so they were not scanned. | All of them, sorted. | PHP |
| `duplicate-declaration` | The same class is declared in two files; the first is used. | The file, then the first one. | PHP |
| `build-output-skipped` | Files in build output folders were left out. | The folders. | TypeScript |
| `non-code-imports` | Imports of non-code files (`./style.css`) gave no edge. | | TypeScript |
| `unmatched-rules` | With `--cluster=rules:<file>`, internal files match no rule and each is its own cluster. | The files, sorted. | all |
| `document-version` | A pairs document has another minor version than this library; it was read anyway. | | all |

### Errors

An error is the reason a command stopped, with exit code 1.

| Code | When | `files` |
| --- | --- | --- |
| `project-unreadable` | The project to scan cannot be used: it is not a folder, or (PHP) has no valid `composer.json`. | |
| `document-unreadable` | The pairs document given cannot be read. | |
| `document-invalid` | The pairs document is not valid JSON or not a pairs document of a version this library reads. | |
| `document-clustered` | The command needs a file-level pairs document and was given a clustered one. | |
| `rules-file-unreadable` | The file of `--cluster=rules:<file>` cannot be read. | |
| `aliases-unusable` | A `--aliases` preset or file cannot be used. | PHP |
| `output-unwritable` | The file of `--output` cannot be written. | |
| `unmatched-rules` | As the warning, with `--strict`. | The files, sorted. |
| `target-not-found` | A `dependents` target matches no node or symbol. | |
| `target-outside-project` | A `dependents` target is an absolute path outside the project folder. | |

## Libraries

Besides the command line, each library gives its callers the diagnostics as
data, so no one has to run the command and read standard error:

| | Scan result | A diagnostic |
| --- | --- | --- |
| PHP | `ScanResult::$diagnostics` | `Untangled\Diagnostic`: `level`, `code`, `message`, `files`; `toArray()`, `toJson()` |
| Python | `ScanResult.diagnostics` | `untangled.diagnostics.Diagnostic`: `level`, `code`, `message`, `files`; `to_dict()`, `to_json()` |
| TypeScript | `ScanResult.diagnostics` | `Diagnostic` (`src/diagnostics.ts`): `level`, `code`, `message`, `files?`; `warningDiagnostic()`, `errorDiagnostic()`, `encodeDiagnostic()` |

The older `warnings` of a scan result, a list of strings, is kept and is the
`message` of each diagnostic whose level is `warning`, in the same order. It
will not gain new meaning; new code should read `diagnostics`.

Reading a pairs document takes a `diagnostics` list next to its older
`warnings` list for the version warning in the same way.

## Conformance

A case may pin the diagnostics of scanning its project in
`<language>/expected/diagnostics.jsonl`, one JSON object per line, in order. A
library passes when the scan gives the same `level`, `code` and `files` in the
same order. The `message` is recorded for people reading the file but is not
compared: it may differ in wording between libraries, and it can carry the
version of a parser or of Python. Conditions that depend on the version of the
language running the scanner, such as code that only a newer Python parses
whole, are not pinned. `scripts/check-cross-language.py` checks that every code
a library writes or a case expects is in the tables above, and that every code
in the tables is written by some library.

## For programs that read the lines

```sh
untangled scan . --diagnostics=json --output=pairs.json 2> diagnostics.jsonl
jq -r 'select(.code == "uncovered-files") | .files[]' diagnostics.jsonl
```

- Read standard error line by line and parse each non-empty line as JSON.
  Branch on `code` and `level`; use `files` for paths. Do not look in `message`.
- Standard output is still the command's result, and the exit code still says
  whether it succeeded; diagnostics do not change either.
- Treat an unknown `code` as a diagnostic of its level. Later versions will add
  codes.
- To turn warnings into failures in CI, fail on `level == "warning"` lines, or
  on a particular `code`, in your own script. (`--strict` does that for
  `unmatched-rules` inside Untangled.)
