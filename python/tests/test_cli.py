# SPDX-License-Identifier: GPL-2.0-only
import io
import json
import subprocess
import sys

from untangled import version
from untangled.cli import USAGE, main


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


def test_analyze_and_report_are_not_there_yet() -> None:
    code, _, err = run("analyze", ".")
    assert code == 2 and "not in the Python library yet" in err


def test_scan_writes_json(project) -> None:
    root = project({"a.py": "import b\n", "b.py": ""})
    code, out, err = run("scan", root)
    assert (code, err) == (0, "")
    assert json.loads(out)["edges"] == [{"from": "a.py", "to": "b.py", "kinds": ["import"], "count": 1}]


def test_scan_writes_snakefood(project) -> None:
    root = project({"a.py": "import b\n", "b.py": ""})
    assert run("scan", root, "--format=snakefood") == (
        0,
        f"(('{root}', 'a.py'), ('{root}', 'b.py'))\n(('{root}', 'b.py'), (None, None))\n",
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
