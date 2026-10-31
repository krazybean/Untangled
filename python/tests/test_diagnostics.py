# SPDX-License-Identifier: GPL-2.0-only
"""Structured diagnostics (spec/diagnostics.md): the value, the scanner's codes and `--diagnostics=json`."""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from untangled.cli import main
from untangled.diagnostics import ERROR, WARNING, Diagnostic
from untangled.graph import PairsDocument
from untangled.scanner.scanner import Scanner

LAYERS = Path(__file__).resolve().parents[2] / "conformance" / "cases" / "layers" / "python"


def run(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(list(args), out, err)
    return code, out.getvalue(), err.getvalue()


def lines(err: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in err.rstrip("\n").split("\n")]


# The value


def test_the_fields_are_written_in_the_specified_order() -> None:
    diagnostic = Diagnostic.warning("uncovered-files", "three files", ["a.py", "b/c.py"])
    assert diagnostic.to_json() == (
        '{"level":"warning","code":"uncovered-files","message":"three files","files":["a.py","b/c.py"]}'
    )
    assert list(diagnostic.to_dict()) == ["level", "code", "message", "files"]


def test_no_files_means_no_files_field() -> None:
    diagnostic = Diagnostic.error("project-unreadable", "not a folder")
    assert diagnostic.to_json() == '{"level":"error","code":"project-unreadable","message":"not a folder"}'
    assert diagnostic.to_text() == "error: not a folder"
    assert Diagnostic.warning("c-d", "x").to_text() == "warning: x"


def test_a_special_message_stays_one_valid_line() -> None:
    message = 'quote " backslash \\ newline \n tab \t cr \r nul \0 unit \x1f slash / unicode é 漢 😀 separator  '
    files = ['dir/na"me\n.py', "ünï/ç.py"]
    text = Diagnostic.warning("some-code", message, files).to_json()
    assert "\n" not in text and "\r" not in text
    decoded = json.loads(text)
    assert decoded["message"] == message and decoded["files"] == files
    # Slashes and non-ASCII are written as they are; control characters are escaped in lower-case hex.
    assert "slash / unicode é 漢 😀" in text and "\\u001f" in text and "\\u0000" in text


def test_text_that_is_not_unicode_is_written_with_the_replacement_character() -> None:
    decoded = json.loads(Diagnostic.warning("some-code", "bad \udcff byte", ["na\udcffme.py"]).to_json())
    assert decoded["message"] == "bad � byte" and decoded["files"] == ["na�me.py"]


# The scanner


def scanned(project, files: dict[str, str], **options: Any) -> list[tuple[str, str, list[str]]]:
    root = project(files)
    result = Scanner(**options).scan(root)
    # The older warnings are the messages of the warning diagnostics, in order.
    assert result.warnings == [item.message for item in result.diagnostics if item.level == WARNING]
    return [(item.level, item.code, item.files) for item in result.diagnostics]


def test_a_clean_scan_has_none(project) -> None:
    assert scanned(project, {"a.py": "x = 1\n"}) == []


def test_a_file_that_does_not_parse(project) -> None:
    assert scanned(project, {"a.py": "x = 1\n", "bad.py": "def (\n"}) == [(WARNING, "file-unparseable", ["bad.py"])]


def test_a_file_read_statement_by_statement(project) -> None:
    files = {"a.py": "import os\nx = = 1\nimport json\n", "ok.py": "import sys\n"}
    assert scanned(project, files) == [(WARNING, "file-partially-parsed", ["a.py"])]


def test_sources_that_do_not_exist_or_leave_the_project(project) -> None:
    assert scanned(project, {"a.py": ""}, sources=["./nope/deeper/", "../outside"]) == [
        (WARNING, "source-not-found", ["nope/deeper"]),
        (WARNING, "source-outside-project", []),
    ]


def test_nothing_to_scan(project) -> None:
    assert scanned(project, {"README.md": ""}) == [(WARNING, "nothing-scanned", [])]


def test_a_broken_pyproject(project) -> None:
    assert scanned(project, {"pyproject.toml": "[project\n", "a.py": ""}) == [
        (WARNING, "config-unreadable", ["pyproject.toml"])
    ]


def test_virtualenvs_that_cannot_be_read(project) -> None:
    assert scanned(project, {".venv/pyvenv.cfg": "", "a.py": ""}) == [
        (WARNING, "venv-without-site-packages", [".venv"])
    ]
    assert scanned(project, {"a.py": ""}, venvs=["nope"]) == [(WARNING, "venv-not-found", ["nope"])]


def test_packages_that_cannot_be_listed(project) -> None:
    assert scanned(project, {"a.py": "import yaml\n"}) == [(WARNING, "package-list-missing", [])]


def test_several_diagnostics_keep_the_order_of_the_scan(project) -> None:
    assert scanned(project, {"bad.py": "def (\n", "pyproject.toml": "[project\n"}, sources=["nope"]) == [
        (WARNING, "config-unreadable", ["pyproject.toml"]),
        (WARNING, "source-not-found", ["nope"]),
        (WARNING, "file-unparseable", ["bad.py"]),
    ]


def test_the_version_of_a_pairs_document() -> None:
    warnings: list[str] = []
    diagnostics: list[Diagnostic] = []
    data = {"format": "untangled-pairs", "version": "0.99", "language": "python", "nodes": [], "edges": []}
    PairsDocument.from_dict(data, warnings, diagnostics)
    assert [(item.level, item.code) for item in diagnostics] == [(WARNING, "document-version")]
    assert warnings == [diagnostics[0].message]


# The command line


def messy(project) -> str:
    return project({"a.py": "x = 1\n", "bad.py": "def (\n", "pyproject.toml": "[project\n"})


def test_text_is_the_default_and_json_says_the_same_thing(project) -> None:
    root = messy(project)
    code, out, text = run("scan", root)
    json_code, json_out, json_err = run("scan", root, "--diagnostics=json")
    assert (code, json_code) == (0, 0)
    assert out == json_out, "standard output is the same in both modes"
    assert run("scan", root, "--diagnostics=text")[2] == text
    text_lines = text.rstrip("\n").split("\n")
    parsed = lines(json_err)
    assert [f"{item['level']}: {item['message']}" for item in parsed] == text_lines
    assert [(item["level"], item["code"], item["files"]) for item in parsed] == [
        (WARNING, "config-unreadable", ["pyproject.toml"]),
        (WARNING, "file-unparseable", ["bad.py"]),
    ]
    assert text_lines[1].startswith("warning: bad.py: cannot parse as Python 3")


def test_the_lines_are_the_same_every_time(project) -> None:
    root = messy(project)
    assert run("scan", root, "--diagnostics=json") == run("scan", root, "--diagnostics=json")


@pytest.mark.parametrize("fmt", ["text", "json"])
def test_no_diagnostics_means_nothing_on_standard_error(fmt: str) -> None:
    code, out, err = run("scan", str(LAYERS / "project"), f"--diagnostics={fmt}")
    assert code == 0 and out and err == ""


@pytest.mark.parametrize(
    "args",
    [
        ["scan", str(LAYERS / "project")],
        ["analyze", str(LAYERS / "expected" / "pairs.json")],
        ["report", str(LAYERS / "expected" / "pairs.json")],
        ["dependents", str(LAYERS / "expected" / "pairs.json"), "src/app/domain/user.py"],
    ],
)
def test_every_command_takes_the_option(args: list[str]) -> None:
    code, out, err = run(*args, "--diagnostics=json")
    assert code == 0 and out and err == ""


@pytest.mark.parametrize("fmt", ["github", "xml", ""])
def test_an_unknown_format_is_a_usage_error(fmt: str) -> None:
    assert run("scan", str(LAYERS / "project"), f"--diagnostics={fmt}") == (
        2,
        "",
        f"Unknown diagnostics format: {fmt} (use text or json)\n",
    )
    code, _, err = run("scan", str(LAYERS / "project"), "--diagnostics")
    assert code == 2 and "Option --diagnostics needs a value" in err


def test_usage_errors_stay_text_in_json_mode() -> None:
    assert run("scan", ".", "--nope", "--diagnostics=json") == (2, "", "Unknown option for scan: --nope\n")


def test_unmatched_rules_are_a_warning_or_with_strict_an_error(tmp_path) -> None:
    pairs = str(LAYERS / "expected" / "pairs.json")
    rules = tmp_path / "rules"
    rules.write_text("src/app/domain/ Core\n", encoding="utf-8")
    code, out, err = run("analyze", pairs, f"--cluster=rules:{rules}", "--diagnostics=json")
    assert code == 0 and out
    line = lines(err)[0]
    assert (line["level"], line["code"]) == (WARNING, "unmatched-rules")
    assert line["files"] == [
        "bootstrap.py",
        "src/app/http/router.py",
        "src/app/http/user_controller.py",
        "src/app/infra/clock.py",
        "src/app/infra/user_repository.py",
    ]
    assert run("analyze", pairs, f"--cluster=rules:{rules}")[2] == f"warning: {line['message']}\n"

    code, out, err = run("analyze", pairs, f"--cluster=rules:{rules}", "--strict", "--diagnostics=json")
    assert (code, out) == (1, "")
    strict = lines(err)
    assert len(strict) == 1 and (strict[0]["level"], strict[0]["code"], strict[0]["files"]) == (
        ERROR,
        "unmatched-rules",
        line["files"],
    )
    assert run("analyze", pairs, f"--cluster=rules:{rules}", "--strict")[2] == f"error: {line['message']}\n"


def test_the_pairs_document_version_is_a_diagnostic(tmp_path) -> None:
    data = json.loads((LAYERS / "expected" / "pairs.json").read_text(encoding="utf-8"))
    data["version"] = "0.99"
    file = tmp_path / "pairs.json"
    file.write_text(json.dumps(data), encoding="utf-8")
    code, _, err = run("analyze", str(file), "--diagnostics=json")
    assert code == 0 and (lines(err)[0]["level"], lines(err)[0]["code"]) == (WARNING, "document-version")


PAIRS = str(LAYERS / "expected" / "pairs.json")


@pytest.mark.parametrize(
    ("args", "code"),
    [
        pytest.param(["scan", "/no/such/folder"], "project-unreadable", id="project"),
        pytest.param(["analyze", "/no/such/folder"], "project-unreadable", id="project, for analyze"),
        pytest.param(["analyze", PAIRS, "--cluster=rules:/no/such/rules"], "rules-file-unreadable", id="rules file"),
        pytest.param(["dependents", PAIRS, "src/nope.py"], "target-not-found", id="target"),
        pytest.param(
            ["dependents", str(LAYERS / "project"), "/no/such/src/app/domain/user.py"],
            "target-outside-project",
            id="target outside",
        ),
        pytest.param(
            ["scan", str(LAYERS / "project"), "--output=/no/such/folder/pairs.json"], "output-unwritable", id="output"
        ),
    ],
)
def test_a_failure_is_the_last_diagnostic_and_an_error(args: list[str], code: str) -> None:
    exit_code, out, err = run(*args, "--diagnostics=json")
    assert (exit_code, out) == (1, "")
    last = lines(err)[-1]
    assert (last["level"], last["code"]) == (ERROR, code)
    # Text mode says the same, as before.
    text_code, _, text = run(*args)
    assert (text_code, text) == (1, f"error: {last['message']}\n")


def test_documents_that_cannot_be_used(tmp_path) -> None:
    (tmp_path / "bad.json").write_text("{nope", encoding="utf-8")
    (tmp_path / "list.json").write_text("[]", encoding="utf-8")
    clustered = {
        "format": "untangled-pairs",
        "version": "0.1",
        "language": "python",
        "nodes": [{"id": "a", "kind": "cluster"}],
        "edges": [],
    }
    (tmp_path / "clustered.json").write_text(json.dumps(clustered), encoding="utf-8")
    for name in ("bad.json", "list.json"):
        code, _, err = run("analyze", str(tmp_path / name), "--diagnostics=json")
        assert code == 1 and (lines(err)[0]["level"], lines(err)[0]["code"]) == (ERROR, "document-invalid")
    code, _, err = run("analyze", str(tmp_path / "clustered.json"), "--diagnostics=json")
    assert code == 1 and lines(err)[0]["code"] == "document-clustered"
    code, _, err = run("dependents", str(tmp_path / "clustered.json"), "a", "--diagnostics=json")
    assert code == 1 and lines(err)[0]["code"] == "document-clustered"
