# SPDX-License-Identifier: GPL-2.0-only
"""Runs the shared cases in conformance/cases (see conformance/README.md): every case with a
python/ folder, scanned with the --source paths in its python/sources file if it has one,
must produce its expected pairs document. Analyses and DOT graphs are checked once the
Python library has analyze and report."""

import json
from pathlib import Path
from typing import Any

import pytest

from untangled.scanner.scanner import Scanner

CASES = Path(__file__).resolve().parents[2] / "conformance" / "cases"
PYTHON_CASES = sorted(path for path in CASES.glob("*/python") if path.is_dir())


def scan(case: Path) -> str:
    sources_file = case / "sources"
    sources = sources_file.read_text(encoding="utf-8").split() if sources_file.is_file() else []
    return Scanner(sources=sources).scan(str(case / "project")).pairs.to_json()


def without_generator(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key != "generator"}


def test_there_are_cases() -> None:
    assert len(PYTHON_CASES) >= 8


@pytest.mark.parametrize("case", PYTHON_CASES, ids=lambda case: case.parent.name)
def test_pairs(case: Path) -> None:
    expected = json.loads((case / "expected" / "pairs.json").read_text(encoding="utf-8"))
    assert without_generator(json.loads(scan(case))) == without_generator(expected)


@pytest.mark.parametrize("case", PYTHON_CASES, ids=lambda case: case.parent.name)
def test_every_case_has_an_expected_analysis(case: Path) -> None:
    assert (case / "expected" / "analysis.json").is_file()


@pytest.mark.parametrize("case", PYTHON_CASES, ids=lambda case: case.parent.name)
def test_scan_is_deterministic(case: Path) -> None:
    assert scan(case) == scan(case)
