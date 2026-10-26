# SPDX-License-Identifier: GPL-2.0-only
"""Runs the shared cases in conformance/cases (see conformance/README.md): every case with a
python/ folder, scanned with the --source paths in its python/sources file if it has one,
must produce its expected pairs document, every expected analysis[.<strategy>].json, and
every expected graph[.<strategy>].dot byte for byte."""

import io
import json
import re
from pathlib import Path
from typing import Any

import pytest

from untangled.analysis.analyzer import analyze
from untangled.analysis.clustering import Clustering
from untangled.analysis.filtering import Filter
from untangled.cli import main
from untangled.graph import PairsDocument, encode
from untangled.report import dot
from untangled.report.report import Report
from untangled.scanner.scanner import Scanner

CASES = Path(__file__).resolve().parents[2] / "conformance" / "cases"
PYTHON_CASES = sorted(path for path in CASES.glob("*/python") if path.is_dir())
ANALYSES = [(case, file) for case in PYTHON_CASES for file in sorted((case / "expected").glob("analysis*.json"))]
DEPENDENTS = [(case, file) for case in PYTHON_CASES for file in sorted((case / "expected").glob("dependents.*"))]
GRAPHS = [(case, file) for case in PYTHON_CASES for file in sorted((case / "expected").glob("graph*.dot"))]


def lines(file: Path) -> list[str]:
    """The non-empty lines of an optional file: one value per line, so a value may hold spaces."""
    return [line for line in file.read_text(encoding="utf-8").splitlines() if line] if file.is_file() else []


def scan(case: Path) -> PairsDocument:
    return Scanner(sources=lines(case / "sources")).scan(str(case / "project")).pairs


def clustering(case: Path, suffix: str) -> Clustering | None:
    """The clustering an expected file's suffix names: "" (none), ".rules", or ".namespace-2" and the like."""
    if suffix == "":
        return None
    if suffix == ".rules":
        return Clustering.parse_rules((case / "clusters.rules").read_text(encoding="utf-8"))
    return Clustering.from_string(re.sub(r"-(?=[0-9]+$)", ":", suffix[1:]))


def comparable(value: Any) -> Any:
    """Equality as the spec defines it for conformance: numbers compare to 4 decimal places."""
    if isinstance(value, dict):
        return {key: comparable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [comparable(item) for item in value]
    if isinstance(value, float):
        return round(value, 4)
    return value


def without_generator(document: dict[str, Any]) -> dict[str, Any]:
    return comparable({key: value for key, value in document.items() if key != "generator"})


def case_id(item: Any) -> str:
    if isinstance(item, Path) and item.name == "python":
        return item.parent.name
    return item.name if isinstance(item, Path) else str(item)


def test_lines_keeps_spaces_and_drops_empty_lines(tmp_path: Path) -> None:
    file = tmp_path / "args"
    file.write_text("--include=docs/a b/**\n\nsrc/My Folder/A.php\r\n", encoding="utf-8")
    assert lines(file) == ["--include=docs/a b/**", "src/My Folder/A.php"]
    assert lines(tmp_path / "missing") == []


def test_there_are_cases() -> None:
    assert len(PYTHON_CASES) >= 8


@pytest.mark.parametrize("case", PYTHON_CASES, ids=case_id)
def test_pairs(case: Path) -> None:
    expected = json.loads((case / "expected" / "pairs.json").read_text(encoding="utf-8"))
    assert without_generator(json.loads(scan(case).to_json())) == without_generator(expected)


@pytest.mark.parametrize("case", PYTHON_CASES, ids=case_id)
def test_every_case_has_an_expected_analysis(case: Path) -> None:
    assert (case / "expected" / "analysis.json").is_file()


@pytest.mark.parametrize("case", PYTHON_CASES, ids=case_id)
def test_scan_is_deterministic(case: Path) -> None:
    assert scan(case).to_json() == scan(case).to_json()


@pytest.mark.parametrize("case", PYTHON_CASES, ids=case_id)
def test_expected_pairs_read_back_unchanged(case: Path) -> None:
    expected = json.loads((case / "expected" / "pairs.json").read_text(encoding="utf-8"))
    assert without_generator(json.loads(PairsDocument.from_dict(expected).to_json())) == without_generator(expected)


@pytest.mark.parametrize(("case", "file"), ANALYSES, ids=case_id)
def test_analysis(case: Path, file: Path) -> None:
    strategy = clustering(case, file.stem[len("analysis") :])
    actual = json.loads(encode(analyze(Filter().apply(scan(case)), strategy)))
    expected = json.loads(file.read_text(encoding="utf-8"))
    assert without_generator(actual) == without_generator(expected)


@pytest.mark.parametrize(("case", "file"), DEPENDENTS, ids=case_id)
def test_dependents(case: Path, file: Path) -> None:
    """Runs `dependents` on the case's expected pairs document with the arguments, one per line, of
    `dependents.<name>.args`. A .json expectation is compared as a document, a .txt one byte for byte."""
    args = lines(case / f"{file.stem}.args")
    out, err = io.StringIO(), io.StringIO()
    assert main(["dependents", str(case / "expected" / "pairs.json"), *args], out, err) == 0, err.getvalue()
    if file.suffix == ".json":
        assert without_generator(json.loads(out.getvalue())) == without_generator(
            json.loads(file.read_text(encoding="utf-8"))
        )
        assert out.getvalue().endswith("}\n")
    else:
        assert out.getvalue() == file.read_text(encoding="utf-8")


@pytest.mark.parametrize(("case", "file"), GRAPHS, ids=case_id)
def test_dot_graph(case: Path, file: Path) -> None:
    strategy = clustering(case, file.stem[len("graph") :])
    report = Report.build(case.parent.name, Filter().apply(scan(case)), strategy)
    assert dot.render(report) == file.read_text(encoding="utf-8")
