# SPDX-License-Identifier: GPL-2.0-only
"""`untangled <command> [options]`. The command and option names are shared by every
Untangled library; this version implements `scan`."""

import sys
from typing import TextIO

from untangled import version
from untangled.scanner.project import ProjectError
from untangled.scanner.scanner import Scanner

USAGE = """\
Usage: untangled scan [<path>] [--dev] [--source=<path>]... [--venv=<path>]...
                      [--format=json|snakefood] [--output=<file>]

Commands:
  scan       Write the dependency pairs of a Python project (default path: .)

Options:
  --dev              Also scan tests (test/ and tests/ folders, test_*.py, *_test.py, conftest.py)
  --source=PATH      Add PATH, a folder relative to the project, to the import roots (repeatable),
                     for code that is importable from a folder the scanner does not find by itself
  --venv=PATH        Read installed packages from this virtualenv instead of the ones found in the
                     project (repeatable)
  --format=FORMAT    json (default, the Untangled pairs document) or snakefood
  --output=FILE      Write to FILE instead of standard output
  -h, --help         Show this help
  -V, --version      Show the version

analyze and report are not in the Python library yet. Meanwhile, the PHP library
reads this library's pairs documents: untangled analyze pairs.json
"""

_COMMANDS = {"scan": {"dev", "source", "venv", "format", "output"}}
_REPEATABLE = {"source", "venv"}


def main(argv: list[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    args = sys.argv[1:] if argv is None else argv

    positional: list[str] = []
    options: dict[str, str | bool] = {}
    repeated: dict[str, list[str]] = {name: [] for name in _REPEATABLE}
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
            if name in _REPEATABLE and has_value:
                repeated[name].append(value)
            continue
        positional.append(arg)

    command = positional.pop(0) if positional else None
    if command in ("analyze", "report"):
        err.write(
            f"{command} is not in the Python library yet; the PHP library's `untangled {command}` reads pairs.json\n"
        )
        return 2
    if command not in _COMMANDS:
        err.write(USAGE if command is None else f"Unknown command: {command}\n\n{USAGE}")
        return 2
    unknown = [name for name in options if name not in _COMMANDS[command]]
    if unknown:
        err.write(f"Unknown option for {command}: --{unknown[0]}\n")
        return 2
    for name, value in options.items():
        if name != "dev" and not isinstance(value, str):
            err.write(f"Option --{name} needs a value, as in --{name}=...\n")
            return 2
    if "dev" in options and options["dev"] is not True:
        err.write("Option --dev takes no value\n")
        return 2
    output_format = options.get("format", "json")
    if output_format not in ("json", "snakefood"):
        err.write(f"Unknown format: {output_format}\n")
        return 2

    path = positional[0] if positional else "."
    scanner = Scanner(dev="dev" in options, sources=repeated["source"], venvs=repeated["venv"] or None)
    try:
        result = scanner.scan(path)
    except ProjectError as error:
        err.write(f"error: {error}\n")
        return 1
    for warning in result.warnings:
        err.write(f"warning: {warning}\n")

    text = result.pairs.to_json() if output_format == "json" else result.pairs.to_snakefood(path)
    output = options.get("output")
    if isinstance(output, str):
        try:
            with open(output, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        except OSError:
            err.write(f"error: cannot write {output}\n")
            return 1
    else:
        out.write(text)
    return 0
