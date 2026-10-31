#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Checks that the libraries agree where the conformance cases say they should: every case
with more than one language folder has, for each expected analysis[.<strategy>].json they
share, the same summary in every language (see conformance/README.md); and the diagnostic
codes the libraries and the conformance cases use are the ones spec/diagnostics.md lists."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "conformance" / "cases"
LANGUAGES = ("php", "python", "typescript")

# The places a library names a diagnostic code: the first string argument of these calls.
_CODE_CALLS = re.compile(
    r"""(?:Diagnostic::(?:warning|error)|Diagnostic\.(?:warning|error)|(?:warning|error)Diagnostic
        |->fail|\bFailure|_Failure|DependentsException|DependentsError)\(\s*['"]([a-z]+(?:-[a-z]+)+)['"]""",
    re.VERBOSE,
)
# DependentsException/DependentsError take the code second, after the message.
_CODE_SECOND = re.compile(r"""(?:DependentsException|DependentsError)\(.*?,\s*['"]([a-z]+(?:-[a-z]+)+)['"]\s*\)""", re.S)


def check_diagnostics() -> int:
    """Every code a library writes, and every code a conformance case expects, is in the spec's tables,
    and every code in the spec is written by some library."""
    spec = (ROOT / "spec" / "diagnostics.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^\| `([a-z]+(?:-[a-z]+)+)` \|", spec, re.M))
    used: dict[str, set[str]] = {}
    sources = ""
    for language, folder, pattern in (
        ("php", "php/src", "*.php"),
        ("python", "python/src/untangled", "*.py"),
        ("typescript", "typescript/src", "*.ts"),
    ):
        for file in sorted((ROOT / folder).rglob(pattern)):
            text = file.read_text(encoding="utf-8")
            sources += text
            for code in _CODE_CALLS.findall(text) + _CODE_SECOND.findall(text):
                used.setdefault(code, set()).add(language)
    status = 0
    for code, languages in sorted(used.items()):
        if code not in documented:
            print(f"diagnostic code {code!r} ({', '.join(sorted(languages))}) is not in spec/diagnostics.md")
            status = 1
    for code in sorted(code for code in documented if f'"{code}"' not in sources and f"'{code}'" not in sources):
        print(f"diagnostic code {code!r} is in spec/diagnostics.md but no library writes it")
        status = 1
    for file in sorted(CASES.glob("*/*/expected/diagnostics.jsonl")):
        for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
            item = json.loads(line)
            if list(item)[:3] != ["level", "code", "message"] or item["level"] not in ("warning", "error"):
                print(f"{file.relative_to(CASES)}:{number}: not a diagnostic as spec/diagnostics.md defines it")
                status = 1
            elif item["code"] not in documented:
                print(f"{file.relative_to(CASES)}:{number}: code {item['code']!r} is not in spec/diagnostics.md")
                status = 1
    if status == 0:
        print(f"diagnostic codes ok ({len(documented)} documented, {len(used)} used)")
    return status


def main() -> int:
    status = 0
    compared = 0
    for case in sorted(path for path in CASES.iterdir() if path.is_dir()):
        languages = [language for language in LANGUAGES if (case / language / "expected").is_dir()]
        if len(languages) < 2:
            continue
        names = sorted(
            {file.name for language in languages for file in (case / language / "expected").glob("analysis*.json")}
        )
        for name in names:
            summaries = {}
            for language in languages:
                file = case / language / "expected" / name
                if file.is_file():
                    summaries[language] = json.loads(file.read_text(encoding="utf-8"))["summary"]
            if len(summaries) < 2:
                continue
            compared += 1
            first, *others = summaries.items()
            for language, summary in others:
                if summary != first[1]:
                    print(f"{case.name}/{name}: the {language} summary differs from the {first[0]} one")
                    for key in sorted(set(summary) | set(first[1])):
                        if summary.get(key) != first[1].get(key):
                            print(f"  {key}: {first[0]} {first[1].get(key)!r}, {language} {summary.get(key)!r}")
                    status = 1
    if status == 0:
        print(f"cross-language summaries ok ({compared} compared)")
    return status | check_diagnostics()


if __name__ == "__main__":
    sys.exit(main())
