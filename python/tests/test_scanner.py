# SPDX-License-Identifier: GPL-2.0-only
import json
import os
from typing import Any

import pytest

from untangled.scanner.scanner import Scanner


def scan(root: str, **options: Any) -> tuple[dict[str, Any], list[str]]:
    result = Scanner(**options).scan(root)
    return result.pairs.to_dict(), result.warnings


def edges(document: dict[str, Any]) -> list[tuple[str, str, list[str], int]]:
    return [(e["from"], e["to"], e["kinds"], e["count"]) for e in document["edges"]]


def targets(document: dict[str, Any], source: str) -> list[str]:
    return [e["to"] for e in document["edges"] if e["from"] == source]


def test_every_scanned_file_is_a_node_with_its_module(project) -> None:
    document, _ = scan(project({"a.py": "", "pkg/__init__.py": "", "pkg/my-script.py": ""}))
    assert document["nodes"] == [
        {"id": "a.py", "kind": "internal", "module": "a"},
        {"id": "pkg/__init__.py", "kind": "internal", "module": "pkg"},
        {"id": "pkg/my-script.py", "kind": "internal"},
    ]
    assert document["language"] == "python"


def test_import_resolves_the_full_dotted_name(project) -> None:
    root = project(
        {"a.py": "import pkg.sub.mod\n", "pkg/__init__.py": "", "pkg/sub/__init__.py": "", "pkg/sub/mod.py": ""}
    )
    assert targets(scan(root)[0], "a.py") == ["pkg/sub/mod.py"]


def test_a_missing_module_in_a_project_package_is_unresolved_not_its_parent(project) -> None:
    root = project({"a.py": "import pkg.missing\nfrom pkg.gone import x\n", "pkg/__init__.py": ""})
    assert targets(scan(root)[0], "a.py") == ["unresolved:module:pkg.gone", "unresolved:module:pkg.missing"]


def test_from_import_prefers_a_submodule_then_the_module(project) -> None:
    root = project({"a.py": "from pkg import sub, name\n", "pkg/__init__.py": "name = 1\n", "pkg/sub.py": ""})
    assert edges(scan(root)[0]) == [
        ("a.py", "pkg/__init__.py", ["from"], 1),
        ("a.py", "pkg/sub.py", ["from"], 1),
    ]


def test_each_imported_name_is_one_reference(project) -> None:
    root = project({"a.py": "from b import x, y, z\n", "b.py": ""})
    assert edges(scan(root)[0]) == [("a.py", "b.py", ["from"], 3)]


def test_star_import_points_at_the_module(project) -> None:
    root = project({"a.py": "from pkg import *\nfrom ns import *\n", "pkg/__init__.py": "", "ns/x.py": ""})
    assert targets(scan(root)[0], "a.py") == ["pkg/__init__.py"]


def test_namespace_packages_point_at_no_file(project) -> None:
    root = project(
        {
            "a.py": "import ns\nimport ns.inner\nfrom ns import inner\nfrom ns import mod, missing\n",
            "ns/mod.py": "",
            "ns/inner/x.py": "",
        }
    )
    assert edges(scan(root)[0]) == [
        ("a.py", "ns/mod.py", ["from"], 1),
        ("a.py", "unresolved:module:ns.missing", ["from"], 1),
    ]


def test_a_package_wins_over_a_module_of_the_same_name(project) -> None:
    root = project({"a.py": "import util\n", "util.py": "", "util/__init__.py": ""})
    assert targets(scan(root)[0], "a.py") == ["util/__init__.py"]


def test_every_root_is_tried(project) -> None:
    root = project(
        {"main.py": "import shop.cart\nimport src.shop.cart\n", "src/shop/__init__.py": "", "src/shop/cart.py": ""}
    )
    assert edges(scan(root)[0]) == [("main.py", "src/shop/cart.py", ["import"], 2)]


def test_an_earlier_root_wins(project) -> None:
    root = project({"main.py": "import tool\n", "tool.py": "", "extra/tool.py": ""})
    assert targets(scan(root, sources=["extra"])[0], "main.py") == ["extra/tool.py"]


def test_relative_imports(project) -> None:
    root = project(
        {
            "pkg/__init__.py": "from . import a\nfrom .a import x\n",
            "pkg/a.py": "from . import b\nfrom .. import top\nfrom .sub.c import y\n",
            "pkg/b.py": "",
            "pkg/sub/__init__.py": "",
            "pkg/sub/c.py": "from ..b import z\nfrom ... import far\n",
            "solo.py": "from . import x\n",
            "my-dir/s.py": "from . import x\n",
        }
    )
    document, _ = scan(root)
    assert targets(document, "pkg/__init__.py") == ["pkg/a.py"]
    assert targets(document, "pkg/a.py") == ["pkg/b.py", "pkg/sub/c.py", "unresolved:module:..top"]
    assert targets(document, "pkg/sub/c.py") == ["pkg/b.py", "unresolved:module:...far"]
    assert targets(document, "solo.py") == ["unresolved:module:.x"]
    assert targets(document, "my-dir/s.py") == ["unresolved:module:.x"]
    assert all("relative" in edge["kinds"] for edge in document["edges"])


def test_builtins_use_the_top_level_name(project) -> None:
    root = project({"a.py": "import os.path\nfrom collections import abc\nimport imp\nimport sys\n"})
    assert targets(scan(root)[0], "a.py") == ["builtin:collections", "builtin:imp", "builtin:os", "builtin:sys"]
    assert {n["id"]: n["kind"] for n in scan(root)[0]["nodes"]}["builtin:os"] == "builtin"


def test_a_project_module_shadows_the_standard_library(project) -> None:
    root = project({"a.py": "import json\nimport json.decoder\n", "json.py": ""})
    assert targets(scan(root)[0], "a.py") == ["json.py", "unresolved:module:json.decoder"]


def test_a_nested_module_does_not_shadow_the_standard_library(project) -> None:
    root = project({"pkg/a.py": "import json\n", "pkg/json.py": ""})
    assert targets(scan(root)[0], "pkg/a.py") == ["builtin:json"]


def test_packages_win_over_a_namespace_package_of_the_same_name(project) -> None:
    root = project(
        {
            "a.py": "import requests\nimport os\n",
            "requests/notes/x.py": "",
            "os/y.py": "",
            "requirements.txt": "requests\n",
        }
    )
    assert targets(scan(root)[0], "a.py") == ["builtin:os", "pypi:requests"]


def test_installed_packages(project) -> None:
    site = ".venv/lib/python3.12/site-packages/PyYAML-6.0.dist-info/"
    root = project(
        {
            ".venv/pyvenv.cfg": "",
            site + "METADATA": "Name: PyYAML\n",
            site + "RECORD": "yaml/__init__.py,,\n",
            "a.py": "import yaml\nimport requests\n",
        }
    )
    document, warnings = scan(root)
    assert targets(document, "a.py") == ["pypi:pyyaml", "unresolved:module:requests"]
    assert {n["id"]: n["kind"] for n in document["nodes"]}["pypi:pyyaml"] == "external"
    assert warnings == []


def test_venv_option_replaces_the_found_ones(project, tmp_path) -> None:
    site = "envs/main/lib/python3.12/site-packages/x-1.0.dist-info/"
    root = project(
        {
            ".venv/pyvenv.cfg": "",
            ".venv/lib/python3.12/site-packages/y-1.0.dist-info/METADATA": "Name: y\n",
            ".venv/lib/python3.12/site-packages/y-1.0.dist-info/RECORD": "y.py,,\n",
            site + "METADATA": "Name: x\n",
            site + "RECORD": "x.py,,\n",
            "a.py": "import x\nimport y\n",
        }
    )
    document, warnings = scan(root, venvs=["envs/main", "nope"])
    assert targets(document, "a.py") == ["pypi:x", "unresolved:module:y"]
    assert warnings == ["--venv=nope: no such folder"]
    absolute = str(tmp_path / "envs" / "main")
    assert targets(scan(root, venvs=[absolute])[0], "a.py") == ["pypi:x", "unresolved:module:y"]


def test_no_virtualenv_warns_about_imports_from_outside_the_project(project) -> None:
    root = project(
        {
            "a.py": "import requests\nimport yaml.loader\nimport flask, b, c, d, e, f\n"
            "import pkg.missing\nfrom . import x\n",
            "pkg/__init__.py": "",
        }
    )
    _, warnings = scan(root)
    assert warnings == [
        "no virtualenv found (a folder with pyvenv.cfg, or --venv=<path>), so imports of b, c, d, e, f and 3 more"
        " could only be matched against declared dependencies by name, and show as unresolved; create the"
        " project's virtualenv first for a complete picture"
    ]


def test_no_warning_when_only_project_imports_are_unresolved(project) -> None:
    root = project({"a.py": "import pkg.missing\nimport ns.missing\n", "pkg/__init__.py": "", "ns/x.py": ""})
    assert scan(root)[1] == []


def test_dynamic_imports(project) -> None:
    root = project(
        {"a.py": 'import importlib\nimportlib.import_module("b")\nimportlib.import_module(name)\n', "b.py": ""}
    )
    assert edges(scan(root)[0]) == [
        ("a.py", "b.py", ["dynamic"], 1),
        ("a.py", "builtin:importlib", ["import"], 1),
        ("a.py", "unresolved:dynamic:name", ["dynamic"], 1),
    ]


def test_kinds_combine_the_statement_and_its_contexts(project) -> None:
    root = project(
        {
            "pkg/__init__.py": "",
            "pkg/a.py": "def f():\n    if TYPE_CHECKING:\n        from . import b\n",
            "pkg/b.py": "",
        }
    )
    assert edges(scan(root)[0]) == [("pkg/a.py", "pkg/b.py", ["from", "local", "relative", "type-checking"], 1)]


def test_tests_are_scanned_with_dev_only(project) -> None:
    root = project({"app.py": "", "tests/test_app.py": "import app\n", "test_x.py": ""})
    assert [n["id"] for n in scan(root)[0]["nodes"]] == ["app.py"]
    assert [n["id"] for n in scan(root, dev=True)[0]["nodes"]] == ["app.py", "test_x.py", "tests/test_app.py"]


def test_a_test_file_imported_by_scanned_code_is_scanned_and_followed(project) -> None:
    root = project(
        {
            "app.py": "import pkg.test.client\n",
            "pkg/__init__.py": "",
            "pkg/test/__init__.py": "",
            "pkg/test/client.py": "from pkg.test import helpers\n",
            "pkg/test/helpers.py": "",
            "pkg/test/test_client.py": "",
        }
    )
    document, _ = scan(root)
    assert [n["id"] for n in document["nodes"]] == [
        "app.py",
        "pkg/__init__.py",
        "pkg/test/client.py",
        "pkg/test/helpers.py",
    ]


def test_a_file_that_does_not_parse_is_a_node_and_a_warning(project) -> None:
    root = project({"old.py": 'import os\nprint "hi"\n', "ok.py": "import old\n"})
    document, warnings = scan(root)
    assert [n["id"] for n in document["nodes"]] == ["ok.py", "old.py"]
    assert edges(document) == [("ok.py", "old.py", ["import"], 1)]
    assert len(warnings) == 1 and warnings[0].startswith("old.py: cannot parse as Python 3: ")


def test_latin_1_names_come_out_as_utf8(project) -> None:
    root = project({"a.py": "from café import x\n".encode("latin-1"), "café.py": ""})
    assert edges(scan(root)[0]) == [("a.py", "café.py", ["from"], 1)]


def test_source_warnings_are_passed_on(project) -> None:
    assert scan(project({"a.py": ""}), sources=["nope"])[1] == ["--source=nope: no such folder in the project"]


def test_scanning_twice_gives_the_same_document(project) -> None:
    root = project({"a.py": "import b, c\nimport os\n", "b.py": "import a\n", "c.py": ""})
    assert Scanner().scan(root).pairs.to_json() == Scanner().scan(root).pairs.to_json()


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="needs POSIX permissions that apply to this user")
def test_an_unreadable_file_is_a_node_and_a_warning(project, tmp_path) -> None:
    root = project({"a.py": "import b\n", "b.py": ""})
    (tmp_path / "a.py").chmod(0)
    document, warnings = scan(root)
    assert [n["id"] for n in document["nodes"]] == ["a.py", "b.py"]
    assert warnings == ["a.py: cannot read it: Permission denied"]


def test_a_pyproject_with_unexpected_types_is_ignored(project) -> None:
    root = project({"pyproject.toml": 'project = "x"\ntool = "y"\n', "a.py": "import b\n", "b.py": ""})
    result = Scanner().scan(root)
    assert [edge["to"] for edge in json.loads(result.pairs.to_json())["edges"]] == ["b.py"]
