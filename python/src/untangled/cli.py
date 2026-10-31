# SPDX-License-Identifier: GPL-2.0-only
"""`untangled <command> [options]`. The command and option names are shared by every
Untangled library: `scan`, `analyze`, `report` and `dependents`."""

import json
import os
import re
import sys
import tomllib
from typing import TextIO

from untangled import version
from untangled.analysis import dependents
from untangled.analysis.analyzer import analyze
from untangled.analysis.clustering import Clustering
from untangled.analysis.filtering import Filter
from untangled.graph import DocumentError, PairsDocument, encode
from untangled.report import dot, html
from untangled.report.report import Report
from untangled.scanner.project import ProjectError
from untangled.scanner.scanner import Scanner

USAGE = """\
Usage: untangled scan [<path>] [--dev] [--source=<path>]... [--venv=<path>]...
                      [--format=json|snakefood] [--output=<file>]
       untangled analyze [<path>|<pairs.json>] [scan options] [--cluster=<strategy>] [--strict]
                         [--include=<glob>]... [--exclude=<glob>]... [--output=<file>]
       untangled report [<path>|<pairs.json>] [--format=html|dot] [--style=classic]
                         [--title=<text>] [analyze options]
       untangled dependents [<path>|<pairs.json>] <file-or-symbol>... [--transitive]
                            [--max-depth=<n>] [--through=<glob>]...
                            [--format=text|json] [analyze options]

Commands:
  scan       Write the dependency pairs of a Python project (default path: .)
  analyze    Write cycles and coupling metrics for a project or a pairs document
  report     Write a readable HTML report (or a Graphviz DOT graph) of the analysis
  dependents List the files that depend on files or declared symbols

Options:
  --dev              Also scan tests (test/ and tests/ folders, test_*.py, *_test.py, conftest.py)
  --source=PATH      Add PATH, a folder relative to the project, to the import roots (repeatable),
                     for code that is importable from a folder the scanner does not find by itself
  --venv=PATH        Read installed packages from this virtualenv instead of the ones found in the
                     project (repeatable)
  --format=FORMAT    scan: json (default, the Untangled pairs document) or snakefood
                     report: html (default) or dot
                     dependents: text (default) or json
  --transitive       dependents: also the files that depend on a dependent, with their depth
  --max-depth=N      dependents: with --transitive, stop after N steps from the targets
  --through=GLOB     dependents: only walk into files matching GLOB (repeatable, any match counts),
                     so nothing is found by way of other files
  --style=STYLE      report --format=dot only: default, or classic for snakefood's
                     black and white sfood-graph look
  --title=TEXT       report only: the report's title (default: the project name in pyproject.toml)
  --cluster=STRATEGY analyze, report: namespace:N, folder:N or rules:<file>
  --strict           analyze, report: with rules:<file>, exit 1 instead of warning when a
                     file matches no rule
  --include=GLOB     analyze, report, dependents: keep files matching GLOB (repeatable, last match wins)
  --exclude=GLOB     analyze, report, dependents: drop files matching GLOB (repeatable, last match wins)
  --output=FILE      Write to FILE instead of standard output
  -h, --help         Show this help
  -V, --version      Show the version
"""

_SCAN = {"dev", "source", "venv"}
_COMMANDS = {
    "scan": _SCAN | {"format", "output"},
    "analyze": _SCAN | {"cluster", "strict", "include", "exclude", "output"},
    "report": _SCAN | {"cluster", "strict", "include", "exclude", "output", "format", "style", "title"},
    "dependents": _SCAN | {"transitive", "max-depth", "through", "include", "exclude", "output", "format"},
}
_REPEATABLE = {"source", "venv", "through"}


class _Usage(Exception):
    """A usage error: exit code 2."""


class _Failure(Exception):
    """An error reading or writing: exit code 1."""


def main(argv: list[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    try:
        return _run(sys.argv[1:] if argv is None else argv, out, err)
    except _Usage as error:
        err.write(f"{error}\n")
        return 2
    except _Failure as error:
        err.write(f"error: {error}\n")
        return 1


def _run(args: list[str], out: TextIO, err: TextIO) -> int:
    positional: list[str] = []
    options: dict[str, str | bool] = {}
    repeated: dict[str, list[str]] = {name: [] for name in _REPEATABLE}
    patterns: list[tuple[str, str]] = []
    for arg in args:
        if arg in ("-h", "--help"):
            out.write(USAGE)
            return 0
        if arg in ("-V", "--version"):
            out.write(f"{version.NAME} {version.VERSION}\n")
            return 0
        if arg.startswith("--"):
            name, has_value, value = arg[2:].partition("=")
            options[name] = value if has_value else True
            if has_value and name in _REPEATABLE:
                repeated[name].append(value)
            elif has_value and name in ("include", "exclude"):
                # Order matters for these, so they are kept as a list rather than by name.
                patterns.append((name, value))
            continue
        positional.append(arg)

    command = positional.pop(0) if positional else None
    if command not in _COMMANDS:
        raise _Usage(USAGE.rstrip("\n") if command is None else f"Unknown command: {command}\n\n{USAGE.rstrip()}")
    unknown = [name for name in options if name not in _COMMANDS[command]]
    if unknown:
        raise _Usage(f"Unknown option for {command}: --{unknown[0]}")
    for name, value in options.items():
        if name not in ("dev", "strict", "transitive") and not isinstance(value, str):
            raise _Usage(f"Option --{name} needs a value, as in --{name}=...")
    if "dev" in options and options["dev"] is not True:
        raise _Usage("Option --dev takes no value")
    if "strict" in options and options["strict"] is not True:
        raise _Usage("Option --strict takes no value")
    if "transitive" in options and options["transitive"] is not True:
        raise _Usage("Option --transitive takes no value")

    path = positional[0] if positional else "."
    scanner = Scanner(dev="dev" in options, sources=repeated["source"], venvs=repeated["venv"] or None)
    output = options.get("output")
    output = output if isinstance(output, str) else None

    if command == "scan":
        output_format = options.get("format", "json")
        if output_format not in ("json", "snakefood"):
            raise _Usage(f"Unknown format: {output_format}")
        pairs = _scan(scanner, path, err)
        return _write(pairs.to_json() if output_format == "json" else pairs.to_snakefood(path), output, out)

    if command == "dependents":
        return _dependents(positional, options, patterns, repeated["through"], scanner, output, out, err)

    output_format = options.get("format", "html")
    if command == "report" and output_format not in ("html", "dot"):
        raise _Usage(f"Unknown format: {output_format}")
    style = options.get("style", "default")
    if style not in dot.STYLES:
        raise _Usage(f"Unknown style: {style}")
    if "style" in options and output_format != "dot":
        raise _Usage("--style only applies to --format=dot")
    strategy = options.get("cluster")
    if "strict" in options and not (isinstance(strategy, str) and strategy.startswith("rules:")):
        raise _Usage("--strict only applies to --cluster=rules:<file>")
    clustering = _clustering(strategy)

    pairs = _load(path, scanner, err)

    selected = _filter(patterns).apply(pairs)
    unmatched = clustering.unmatched(selected) if clustering is not None else []
    if unmatched:
        message = Clustering.describe_unmatched(unmatched)
        if "strict" in options:
            raise _Failure(message)
        err.write(f"warning: {message}\n")
    try:
        if command == "analyze":
            return _write(encode(analyze(selected, clustering)), output, out)
        title = options.get("title")
        report = Report.build(title if isinstance(title, str) else _title(path), selected, clustering)
    except ValueError as error:
        raise _Failure(str(error)) from error
    return _write(dot.render(report, str(style)) if output_format == "dot" else html.render(report), output, out)


def _dependents(
    positional: list[str],
    options: dict[str, str | bool],
    patterns: list[tuple[str, str]],
    through: list[str],
    scanner: Scanner,
    output: str | None,
    out: TextIO,
    err: TextIO,
) -> int:
    """The source is the first argument when it is a folder or a .json file, else the current folder;
    the rest are the targets."""
    output_format = options.get("format", "text")
    if output_format not in ("text", "json"):
        raise _Usage(f"Unknown format: {output_format}")
    max_depth = None
    if "max-depth" in options:
        given = str(options["max-depth"])
        if not re.fullmatch(r"[1-9][0-9]*", given):
            raise _Usage(f'Option --max-depth needs a positive integer, as in --max-depth=2 (got "{given}")')
        if "transitive" not in options:
            raise _Usage("--max-depth only applies with --transitive")
        # More than 9 digits is deeper than any graph, so it is the same as no limit.
        max_depth = 999999999 if len(given) > 9 else int(given)
    first = positional[0] if positional else None
    has_source = first is not None and (
        os.path.isdir(first) or (os.path.isfile(first) and first.lower().endswith(".json"))
    )
    targets = positional[1:] if has_source else positional
    if not targets:
        raise _Usage("dependents needs at least one file or symbol to look up")
    pairs = _load(first if has_source and first is not None else ".", scanner, err)
    # Absolute paths are relative to the project when the source is one, else to the current folder.
    root = os.path.realpath(first if has_source and first is not None and os.path.isdir(first) else ".")
    try:
        document = dependents.find(
            pairs, targets, "transitive" in options, _filter(patterns), through=through, max_depth=max_depth, root=root
        )
    except ValueError as error:
        raise _Failure(str(error)) from error
    return _write(encode(document) if output_format == "json" else dependents.render_text(document), output, out)


def _filter(patterns: list[tuple[str, str]]) -> Filter:
    """The --include / --exclude globs, in command-line order."""
    selection = Filter()
    for kind, glob in patterns:
        selection.include(glob) if kind == "include" else selection.exclude(glob)
    return selection


def _load(path: str, scanner: Scanner, err: TextIO) -> PairsDocument:
    """Reads a pairs document, or scans a project, and writes the warnings to standard error."""
    if not os.path.isfile(path):
        return _scan(scanner, path, err)
    warnings: list[str] = []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        pairs = PairsDocument.from_dict(data, warnings)
    except OSError as error:
        raise _Failure(f"cannot read {path}") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise _Failure(f"{path} is not valid JSON: {error}") from error
    except DocumentError as error:
        raise _Failure(str(error)) from error
    for warning in warnings:
        err.write(f"warning: {warning}\n")
    return pairs


def _scan(scanner: Scanner, path: str, err: TextIO) -> PairsDocument:
    try:
        result = scanner.scan(path)
    except ProjectError as error:
        raise _Failure(str(error)) from error
    for warning in result.warnings:
        err.write(f"warning: {warning}\n")
    return result.pairs


def _clustering(strategy: str | bool | None) -> Clustering | None:
    if not isinstance(strategy, str):
        return None
    if strategy.startswith("rules:"):
        rules_file = strategy[len("rules:") :]
        try:
            with open(rules_file, encoding="utf-8") as handle:
                text = handle.read()
        except (OSError, UnicodeDecodeError) as error:
            raise _Failure(f"cannot read rules file {rules_file}") from error
        try:
            return Clustering.parse_rules(text)
        except ValueError as error:
            raise _Usage(f"error: {error}") from error
    try:
        return Clustering.from_string(strategy)
    except ValueError as error:
        raise _Usage(f"error: {error}") from error


def _title(path: str) -> str:
    """The default report title: the project name in pyproject.toml, else the folder or file name."""
    if os.path.isfile(path):
        return os.path.basename(path)
    try:
        with open(os.path.join(path, "pyproject.toml"), "rb") as handle:
            name = tomllib.load(handle).get("project", {}).get("name")
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError, AttributeError):
        name = None
    if isinstance(name, str) and name:
        return name
    return os.path.basename(os.path.abspath(path))


def _write(text: str, output: str | None, out: TextIO) -> int:
    if output is None:
        out.write(text)
        return 0
    try:
        with open(output, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except OSError as error:
        raise _Failure(f"cannot write {output}") from error
    return 0
