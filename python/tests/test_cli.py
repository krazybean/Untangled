# SPDX-License-Identifier: GPL-2.0-only
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from untangled import version
from untangled.cli import USAGE, main

LAYERS = Path(__file__).resolve().parents[2] / "conformance" / "cases" / "layers" / "python"
THREE_CYCLE = LAYERS.parent.parent / "three-cycle" / "python"


def run(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(list(args), out, err)
    return code, out.getvalue(), err.getvalue()


def test_help_and_version() -> None:
    assert run("--help") == (0, USAGE, "")
    assert run("scan", "-h") == (0, USAGE, "")
    assert run("-V") == (0, f"untangled-python {version.VERSION}\n", "")


def test_no_command_prints_usage() -> None:
    assert run() == (2, "", USAGE)


def test_unknown_command() -> None:
    code, _, err = run("graph")
    assert code == 2 and err.startswith("Unknown command: graph\n")


def test_scan_writes_json(project) -> None:
    root = project({"a.py": "import b\n", "b.py": ""})
    code, out, err = run("scan", root)
    assert (code, err) == (0, "")
    assert json.loads(out)["edges"] == [{"from": "a.py", "to": "b.py", "kinds": ["import"], "count": 1}]


def test_scan_writes_snakefood(project) -> None:
    root = project({"a.py": "import b\n", "b.py": ""})
    quoted = root.replace("\\", "\\\\")  # a Windows path has backslashes, which the format doubles
    assert run("scan", root, "--format=snakefood") == (
        0,
        f"(('{quoted}', 'a.py'), ('{quoted}', 'b.py'))\n(('{quoted}', 'b.py'), (None, None))\n",
        "",
    )


def test_scan_writes_to_a_file(project, tmp_path) -> None:
    root = project({"a.py": ""})
    output = tmp_path / "pairs.json"
    assert run("scan", root, f"--output={output}") == (0, "", "")
    assert json.loads(output.read_text(encoding="utf-8"))["nodes"][0]["id"] == "a.py"
    code, _, err = run("scan", root, f"--output={tmp_path}/missing/pairs.json")
    assert code == 1 and err.startswith("error: cannot write ")


def test_scan_options(project) -> None:
    root = project({"tests/test_a.py": "import tool\n", "extra/tool.py": ""})
    code, out, err = run("scan", root, "--dev", "--source=extra", "--source=nope")
    assert code == 0
    assert json.loads(out)["edges"][0]["to"] == "extra/tool.py"
    assert err == "warning: --source=nope: no such folder in the project\n"


def test_scan_venv_option(project) -> None:
    root = project({"a.py": "", ".venv/pyvenv.cfg": ""})
    code, _, err = run("scan", root, "--venv=elsewhere")
    assert code == 0 and err == "warning: --venv=elsewhere: no such folder\n"


def test_option_errors(project) -> None:
    root = project({"a.py": ""})
    assert run("scan", root, "--cluster=namespace:2") == (2, "", "Unknown option for scan: --cluster\n")
    assert run("scan", root, "--format") == (2, "", "Option --format needs a value, as in --format=...\n")
    assert run("scan", root, "--dev=yes") == (2, "", "Option --dev takes no value\n")
    assert run("scan", root, "--format=xml") == (2, "", "Unknown format: xml\n")


def test_a_missing_project_is_an_error(tmp_path) -> None:
    code, _, err = run("scan", str(tmp_path / "nope"))
    assert code == 1 and err.startswith("error: ") and "is not a folder" in err


def test_warnings_go_to_stderr(project) -> None:
    root = project({"a.py": 'print "hi"\n'})
    code, out, err = run("scan", root)
    assert code == 0 and json.loads(out)["edges"] == []
    assert err.startswith("warning: a.py: cannot parse as Python 3: ")


def test_python_dash_m(project) -> None:
    root = project({"a.py": ""})
    result = subprocess.run([sys.executable, "-m", "untangled", "scan", root], capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)["language"] == "python"


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def without_generator(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key != "generator"}


def unit_ids(*args: str) -> list[str]:
    code, out, _ = run("analyze", *args)
    assert code == 0
    return [unit["id"] for unit in json.loads(out)["units"]]


def pairs_file(tmp_path: Path, document: Any) -> str:
    path = tmp_path / "pairs.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(path)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        pytest.param(
            ["analyze", ".", "--format=snakefood"], "Unknown option for analyze: --format\n", id="analyze format"
        ),
        pytest.param(["analyze", ".", "--title=x"], "Unknown option for analyze: --title\n", id="analyze title"),
        pytest.param(["analyze", ".", "--style=classic"], "Unknown option for analyze: --style\n", id="analyze style"),
        pytest.param(
            ["analyze", ".", "--cluster"], "Option --cluster needs a value, as in --cluster=...\n", id="no value"
        ),
        pytest.param(
            ["report", ".", "--dev", "--format=snakefood"], "Unknown format: snakefood\n", id="report snakefood"
        ),
        pytest.param(["report", ".", "--format=json"], "Unknown format: json\n", id="report json"),
        pytest.param(["report", ".", "--format=dot", "--style=pastel"], "Unknown style: pastel\n", id="unknown style"),
        pytest.param(
            ["report", ".", "--style=classic"], "--style only applies to --format=dot\n", id="style without dot"
        ),
        pytest.param(
            ["report", ".", "--format=html", "--style=default"],
            "--style only applies to --format=dot\n",
            id="style with html",
        ),
        pytest.param(
            ["analyze", ".", "--cluster=files:2"],
            'error: unknown clustering "files:2" (use namespace:N, folder:N or rules:<file>)\n',
            id="unknown clustering",
        ),
        pytest.param(
            ["report", ".", "--cluster=namespace:0"],
            'error: unknown clustering "namespace:0" (use namespace:N, folder:N or rules:<file>)\n',
            id="depth zero",
        ),
    ],
)
def test_bad_analyze_and_report_options_exit_with_two(args: list[str], message: str) -> None:
    assert run(*args) == (2, "", message)


def test_malformed_rules_exit_with_two(tmp_path) -> None:
    rules = tmp_path / "bad.rules"
    rules.write_text("src/ core\nlib/\n", encoding="utf-8")
    assert run("analyze", str(LAYERS / "project"), f"--cluster=rules:{rules}") == (
        2,
        "",
        'error: rules line 2 must be "<prefix> <cluster>"\n',
    )


def test_a_missing_rules_file_is_an_error(tmp_path) -> None:
    missing = tmp_path / "no.rules"
    assert run("analyze", ".", f"--cluster=rules:{missing}") == (1, "", f"error: cannot read rules file {missing}\n")
    code, _, err = run("analyze", ".", f"--cluster=rules:{tmp_path}")
    assert code == 1 and err == f"error: cannot read rules file {tmp_path}\n"


def rules_file(tmp_path: Path, text: str) -> str:
    path = tmp_path / "t.rules"
    path.write_text(text, encoding="utf-8")
    return f"--cluster=rules:{path}"


def test_unmatched_nodes_warn_and_still_write_the_output(tmp_path) -> None:
    code, out, err = run(
        "analyze", str(LAYERS / "expected" / "pairs.json"), rules_file(tmp_path, "src/app/domain/ core\n")
    )
    assert code == 0
    assert err.startswith("warning: rules: ")
    assert " match no rule and each becomes its own cluster: bootstrap.py, src/app/http/" in err
    assert json.loads(out)["clustering"] == "rules"


def test_no_warning_when_every_node_matches(tmp_path) -> None:
    rules = rules_file(tmp_path, "src/ core\nbootstrap.py boot\n")
    assert run("analyze", str(LAYERS / "expected" / "pairs.json"), rules, "--strict")[::2] == (0, "")


@pytest.mark.parametrize("command", ["analyze", "report"])
def test_strict_fails_on_unmatched_nodes_and_writes_nothing(command: str, tmp_path) -> None:
    rules = rules_file(tmp_path, "src/app/domain/ core\n")
    code, out, err = run(command, str(LAYERS / "expected" / "pairs.json"), rules, "--strict")
    assert (code, out) == (1, "")
    assert err.startswith("error: rules: ") and "warning:" not in err


def test_unmatched_nodes_are_counted_after_filtering(tmp_path) -> None:
    rules = rules_file(tmp_path, "src/app/domain/ core\n")
    args = ("--exclude=src/app/http/**", "--exclude=src/app/infra/**", "--exclude=bootstrap.py", "--strict")
    assert run("analyze", str(LAYERS / "expected" / "pairs.json"), rules, *args)[::2] == (0, "")


@pytest.mark.parametrize(
    ("args", "message"),
    [
        pytest.param(
            ["analyze", ".", "--strict"], "--strict only applies to --cluster=rules:<file>", id="no clustering"
        ),
        pytest.param(
            ["analyze", ".", "--cluster=folder:1", "--strict"],
            "--strict only applies to --cluster=rules:<file>",
            id="folder clustering",
        ),
        pytest.param(["report", ".", "--strict"], "--strict only applies to --cluster=rules:<file>", id="report"),
        pytest.param(
            ["analyze", ".", "--cluster=rules:x", "--strict=yes"], "Option --strict takes no value", id="value"
        ),
        pytest.param(["scan", ".", "--strict"], "Unknown option for scan: --strict", id="scan"),
    ],
)
def test_strict_needs_rules_clustering(args: list[str], message: str) -> None:
    code, _, err = run(*args)
    assert code == 2 and message in err


def test_dependents_of_a_file_in_a_pairs_document() -> None:
    pairs = str(LAYERS / "expected" / "pairs.json")
    code, out, err = run("dependents", pairs, "src/app/domain/user.py")
    assert (code, err) == (0, "")
    assert out == (
        "2 dependents of src/app/domain/user.py\n"
        "\nsrc/app/domain/\n  order.py\n"
        "\nsrc/app/infra/\n  user_repository.py\n"
    )


def test_dependents_scans_a_project() -> None:
    code, out, _ = run("dependents", str(LAYERS / "project"), "src/app/domain/user.py", "--format=json")
    assert code == 0
    assert [item["id"] for item in json.loads(out)["dependents"]] == [
        "src/app/domain/order.py",
        "src/app/infra/user_repository.py",
    ]


def test_dependents_takes_the_current_folder_when_the_first_argument_is_a_target(monkeypatch) -> None:
    monkeypatch.chdir(LAYERS / "project")
    code, out, _ = run("dependents", "src/app/domain/user.py", "--format=json")
    assert code == 0
    assert len(json.loads(out)["dependents"]) == 2


def test_dependents_writes_to_a_file(tmp_path) -> None:
    target = tmp_path / "out.json"
    pairs = str(LAYERS / "expected" / "pairs.json")
    assert run("dependents", pairs, "src/app/domain/user.py", "--format=json", f"--output={target}") == (0, "", "")
    assert json.loads(target.read_text(encoding="utf-8"))["format"] == "untangled-dependents"


def test_dependents_fails_on_an_unknown_target() -> None:
    pairs = str(LAYERS / "expected" / "pairs.json")
    assert run("dependents", pairs, "src/nope.py") == (
        1,
        "",
        'error: no node or symbol "src/nope.py" in the pairs document\n',
    )


def test_dependents_refuses_a_clustered_document(tmp_path) -> None:
    document = {
        "format": "untangled-pairs",
        "version": "0.1",
        "language": "python",
        "nodes": [{"id": "core", "kind": "cluster", "members": ["a.py"]}],
        "edges": [],
    }
    code, _, err = run("dependents", pairs_file(tmp_path, document), "core")
    assert code == 1 and "already clustered" in err


@pytest.mark.parametrize(
    ("args", "message"),
    [
        pytest.param(["dependents", "PAIRS"], "dependents needs at least one file or symbol", id="no target"),
        pytest.param(["dependents", "PAIRS", "a.py", "--format=html"], "Unknown format: html", id="format"),
        pytest.param(
            ["dependents", "PAIRS", "a.py", "--transitive=yes"], "Option --transitive takes no value", id="value"
        ),
        pytest.param(
            ["dependents", "PAIRS", "a.py", "--cluster=folder:1"],
            "Unknown option for dependents: --cluster",
            id="cluster",
        ),
        pytest.param(["analyze", "PAIRS", "--transitive"], "Unknown option for analyze: --transitive", id="analyze"),
    ],
)
def test_dependents_usage_errors(args: list[str], message: str) -> None:
    pairs = str(LAYERS / "expected" / "pairs.json")
    code, _, err = run(*[pairs if arg == "PAIRS" else arg for arg in args])
    assert code == 2 and message in err


def test_analyze_a_project() -> None:
    code, out, err = run("analyze", str(LAYERS / "project"))
    assert (code, err) == (0, "")
    assert out.endswith("}\n") and out.startswith('{\n  "format": "untangled-analysis",\n')
    assert without_generator(json.loads(out)) == without_generator(read(LAYERS / "expected" / "analysis.json"))


def test_analyze_a_pairs_document() -> None:
    code, out, err = run("analyze", str(LAYERS / "expected" / "pairs.json"))
    assert (code, err) == (0, "")
    assert without_generator(json.loads(out)) == without_generator(read(LAYERS / "expected" / "analysis.json"))


@pytest.mark.parametrize(
    ("strategy", "expected"),
    [
        ("namespace:2", "analysis.namespace-2.json"),
        ("folder:1", "analysis.folder-1.json"),
        (f"rules:{LAYERS / 'clusters.rules'}", "analysis.rules.json"),
    ],
)
def test_analyze_with_a_clustering(strategy: str, expected: str) -> None:
    for source in (LAYERS / "project", LAYERS / "expected" / "pairs.json"):
        code, out, err = run("analyze", str(source), f"--cluster={strategy}")
        # bootstrap.py matches no rule (the case keeps it as its own cluster), which the CLI says.
        warning = "warning: rules: 1 file matches no rule and becomes its own cluster: bootstrap.py\n"
        assert (code, err) == (0, warning if strategy.startswith("rules:") else "")
        assert without_generator(json.loads(out)) == without_generator(read(LAYERS / "expected" / expected))


def test_analyze_applies_include_and_exclude_in_order() -> None:
    project = str(LAYERS / "project")
    kept = unit_ids(project, "--exclude=src/app/http/**", "--include=src/app/http/router.py")
    assert "src/app/http/router.py" in kept
    assert "src/app/http/user_controller.py" not in kept
    assert "src/app/domain/user.py" in kept
    reversed_order = unit_ids(project, "--include=src/app/http/router.py", "--exclude=src/app/http/**")
    assert "src/app/http/router.py" not in reversed_order
    assert len(unit_ids(project, "--exclude=**")) == 0


def test_analyze_a_file_that_is_not_json() -> None:
    code, out, err = run("analyze", __file__)
    assert (code, out) == (1, "")
    assert err.startswith(f"error: {__file__} is not valid JSON: ")


def test_analyze_a_document_of_another_format() -> None:
    code, out, err = run("analyze", str(LAYERS / "expected" / "analysis.json"))
    assert (code, out) == (1, "")
    assert err == 'error: not an Untangled pairs document (expected "format": "untangled-pairs")\n'


@pytest.mark.parametrize("command", ["analyze", "report"])
def test_an_invalid_pairs_document_is_an_error(tmp_path, command: str) -> None:
    document = read(LAYERS / "expected" / "pairs.json")
    document["edges"].append({"from": "bootstrap.py", "to": "nowhere.py"})
    code, out, err = run(command, pairs_file(tmp_path, document))
    assert (code, out) == (1, "")
    assert err == "error: edge bootstrap.py -> nowhere.py names a node that is not in the document\n"


def test_analyze_warns_on_an_unknown_minor_version(tmp_path) -> None:
    document = read(THREE_CYCLE / "expected" / "pairs.json")
    document["version"] = "0.9"
    code, out, err = run("analyze", pairs_file(tmp_path, document))
    assert code == 0
    assert err == f"warning: pairs document version 0.9 is newer or older than {version.SPEC}; reading it anyway\n"
    assert json.loads(out)["summary"]["cycles"] == 1


def test_analyze_refuses_a_clustered_document(tmp_path) -> None:
    document = {
        "format": "untangled-pairs",
        "version": version.SPEC,
        "language": "python",
        "nodes": [{"id": "app", "kind": "cluster", "members": ["a.py"]}],
        "edges": [],
    }
    code, out, err = run("analyze", pairs_file(tmp_path, document))
    assert (code, out) == (1, "")
    assert err.startswith("error: the pairs document is already clustered")


def test_analyze_a_missing_project(tmp_path) -> None:
    code, out, err = run("analyze", str(tmp_path / "nope"))
    assert (code, out) == (1, "")
    assert err.startswith("error: ") and "is not a folder" in err


def test_analyze_passes_scan_options_and_warnings(project) -> None:
    root = project({"tests/test_a.py": "import tool\n", "extra/tool.py": ""})
    code, out, err = run("analyze", root, "--dev", "--source=extra", "--source=nope")
    assert code == 0
    assert err == "warning: --source=nope: no such folder in the project\n"
    assert [unit["id"] for unit in json.loads(out)["units"]] == ["extra/tool.py", "tests/test_a.py"]


def test_analyze_writes_to_a_file(tmp_path) -> None:
    output = tmp_path / "analysis.json"
    assert run("analyze", str(THREE_CYCLE / "project"), f"--output={output}") == (0, "", "")
    assert without_generator(read(output)) == without_generator(read(THREE_CYCLE / "expected" / "analysis.json"))


def test_report_defaults_to_html() -> None:
    code, out, err = run("report", str(LAYERS / "project"))
    assert (code, err) == (0, "")
    assert out.startswith("<!doctype html>")
    assert "1 dependency cycle found." in out


def test_report_dot() -> None:
    expected = (LAYERS / "expected" / "graph.namespace-2.dot").read_text(encoding="utf-8")
    for args in (
        ["--format=dot", "--cluster=namespace:2"],
        ["--format=dot", "--style=default", "--cluster=namespace:2"],
    ):
        assert run("report", str(LAYERS / "project"), *args) == (0, expected, "")


def test_report_dot_of_a_pairs_document() -> None:
    expected = (LAYERS / "expected" / "graph.dot").read_text(encoding="utf-8")
    assert run("report", str(LAYERS / "expected" / "pairs.json"), "--format=dot") == (0, expected, "")


def test_report_classic_style() -> None:
    code, out, err = run("report", str(LAYERS / "project"), "--format=dot", "--style=classic")
    assert (code, err) == (0, "")
    assert "node [shape=ellipse, style=filled, fillcolor=lightgrey" in out
    assert '"unresolved:module:app.cache.store" [fillcolor=white];' in out
    assert "#d03b3b" not in out


def test_report_title_defaults_to_the_project_name_in_pyproject(project) -> None:
    root = project({"pyproject.toml": '[project]\nname = "shop & co"\n', "a.py": ""})
    code, out, _ = run("report", root)
    assert code == 0
    assert "<h1>shop &amp; co</h1>" in out
    assert "<title>Dependencies: shop &amp; co</title>" in out


@pytest.mark.parametrize(
    "pyproject",
    [
        pytest.param(None, id="no pyproject"),
        pytest.param("[tool.ruff]\nline-length = 1\n", id="no project table"),
        pytest.param('[project]\nname = ""\n', id="empty name"),
        pytest.param("[project]\nname = 3\n", id="name not a string"),
        pytest.param("not toml [", id="invalid toml"),
    ],
)
def test_report_title_falls_back_to_the_folder_name(project, tmp_path, pyproject: str | None) -> None:
    files = {"a.py": ""} | ({} if pyproject is None else {"pyproject.toml": pyproject})
    code, out, _ = run("report", project(files))
    assert code == 0
    assert f"<h1>{tmp_path.name}</h1>" in out


def test_report_reads_a_pairs_document_and_takes_a_title() -> None:
    pairs = str(LAYERS / "expected" / "pairs.json")
    code, out, _ = run("report", pairs, "--title=Layers & co")
    assert code == 0
    assert "<h1>Layers &amp; co</h1>" in out
    assert "<h1>pairs.json</h1>" in run("report", pairs)[1]


def test_report_applies_clustering_and_filters() -> None:
    code, out, _ = run("report", str(LAYERS / "project"), "--format=dot", "--exclude=src/app/http/**")
    assert code == 0
    assert "src/app/http/" not in out
    assert '"src/app/domain/user.py"' in out
    grouped = run("report", str(LAYERS / "project"), "--cluster=folder:1")[1]
    assert 'id="groups"' in grouped
    assert "share the first 1 level of their folder path" in grouped


def test_report_refuses_a_clustered_document(tmp_path) -> None:
    document = {
        "format": "untangled-pairs",
        "version": version.SPEC,
        "language": "python",
        "nodes": [{"id": "app", "kind": "cluster", "members": ["a.py"]}],
        "edges": [],
    }
    code, _, err = run("report", pairs_file(tmp_path, document))
    assert code == 1 and err.startswith("error: the pairs document is already clustered")


def test_report_writes_to_a_file(tmp_path) -> None:
    output = tmp_path / "report.html"
    assert run("report", str(THREE_CYCLE / "project"), f"--output={output}") == (0, "", "")
    assert output.read_text(encoding="utf-8").startswith("<!doctype html>")
    dot_output = tmp_path / "graph.dot"
    assert run("report", str(THREE_CYCLE / "project"), "--format=dot", f"--output={dot_output}") == (0, "", "")
    assert dot_output.read_text(encoding="utf-8") == (THREE_CYCLE / "expected" / "graph.dot").read_text(
        encoding="utf-8"
    )
    code, _, err = run("report", str(THREE_CYCLE / "project"), f"--output={tmp_path}/missing/report.html")
    assert code == 1 and err == f"error: cannot write {tmp_path}/missing/report.html\n"
