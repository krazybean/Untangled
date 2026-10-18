#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Checks that the libraries agree where the conformance cases say they should: every case
with more than one language folder has, for each expected analysis[.<strategy>].json they
share, the same summary in every language (see conformance/README.md)."""

import json
import sys
from pathlib import Path

CASES = Path(__file__).resolve().parents[1] / "conformance" / "cases"
LANGUAGES = ("php", "python", "typescript")


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
    return status


if __name__ == "__main__":
    sys.exit(main())
