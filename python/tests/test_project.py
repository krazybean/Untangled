# SPDX-License-Identifier: GPL-2.0-only
import os

import pytest

from untangled.scanner.project import Project, ProjectError, is_test_file, module_name


def test_files_are_every_py_file_except_skipped_folders(project) -> None:
    root = project(
        {
            "a.py": "",
            "pkg/__init__.py": "",
            "pkg/b.py": "",
            "pkg/notes.txt": "",
            "pkg/build/c.py": "",
            ".hidden/x.py": "",
            "pkg/__pycache__/x.py": "",
            "node_modules/x.py": "",
            "lib/site-packages/x.py": "",
            "thing.egg-info/x.py": "",
            "build/x.py": "",
            "dist/x.py": "",
            "env/pyvenv.cfg": "",
            "env/lib/x.py": "",
            "deep/venv/pyvenv.cfg": "",
            "deep/venv/x.py": "",
        }
    )
    loaded = Project.load(root)
    assert loaded.files == ["a.py", "pkg/__init__.py", "pkg/b.py", "pkg/build/c.py"]
    assert loaded.venvs == ["env"]
    assert loaded.path("pkg/b.py") == os.path.join(root, "pkg", "b.py")
    assert loaded.has_file("a.py") and not loaded.has_file("build/x.py")


def test_tests_are_listed_but_marked(project) -> None:
    root = project(
        {
            "app.py": "",
            "tests/test_app.py": "",
            "tests/helpers.py": "",
            "pkg/test/client.py": "",
            "pkg/test_thing.py": "",
            "pkg/thing_test.py": "",
            "pkg/conftest.py": "",
            "pkg/testing.py": "",
            "pkg/latest.py": "",
        }
    )
    loaded = Project.load(root)
    assert loaded.tests == {
        "tests/test_app.py",
        "tests/helpers.py",
        "pkg/test/client.py",
        "pkg/test_thing.py",
        "pkg/thing_test.py",
        "pkg/conftest.py",
    }
    assert "pkg/testing.py" in loaded.files and "pkg/testing.py" not in loaded.tests


@pytest.mark.parametrize(
    ("name", "expected"),
    [("test_a.py", True), ("a_test.py", True), ("conftest.py", True), ("testing.py", False), ("contest.py", False)],
)
def test_is_test_file(name: str, expected: bool) -> None:
    assert is_test_file(name) is expected


def test_roots_default_to_the_project_root(project) -> None:
    assert Project.load(project({"a.py": ""})).roots == [""]


def test_src_is_a_root_unless_it_is_a_package(project) -> None:
    assert Project.load(project({"src/shop/__init__.py": ""})).roots == ["src", ""]


def test_src_that_is_a_package_is_not_a_root(project) -> None:
    assert Project.load(project({"src/__init__.py": ""})).roots == [""]


def test_roots_from_pyproject_and_sources_come_first(project) -> None:
    root = project(
        {
            "pyproject.toml": """
                [tool.setuptools]
                package-dir = {"" = "code"}
                [tool.setuptools.packages.find]
                where = ["lib", "missing", "src"]
            """,
            "code/a.py": "",
            "lib/b.py": "",
            "src/c.py": "",
            "extra/d.py": "",
        }
    )
    assert Project.load(root, ["extra", "./extra/"]).roots == ["extra", "code", "lib", "src", ""]


def test_bad_sources_are_warnings(project) -> None:
    root = project({"a.py": "", "file.py": ""})
    loaded = Project.load(root, ["nope", "file.py", "../outside", "."])
    assert loaded.warnings == [
        "--source=nope: no such folder in the project",
        "--source=file.py: no such folder in the project",
        "--source=../outside: outside the project, ignored",
    ]
    assert loaded.roots == [""]


def test_a_broken_pyproject_is_a_warning(project) -> None:
    loaded = Project.load(project({"pyproject.toml": "[project\n", "a.py": ""}))
    assert loaded.pyproject == {}
    assert loaded.warnings[0].startswith("pyproject.toml: cannot read it")


def test_a_missing_folder_is_an_error(tmp_path) -> None:
    with pytest.raises(ProjectError, match="is not a folder"):
        Project.load(str(tmp_path / "nope"))


@pytest.mark.parametrize(
    ("file", "root", "expected"),
    [
        ("shop/cart.py", "", "shop.cart"),
        ("shop/__init__.py", "", "shop"),
        ("src/shop/cart.py", "src", "shop.cart"),
        ("src/shop/cart.py", "", "src.shop.cart"),
        ("manage.py", "", "manage"),
        ("__init__.py", "", None),
        ("scripts/my-tool.py", "", None),
        ("pkg/class.py", "", None),
        ("pkg/café.py", "", "pkg.café"),
        ("2fa/x.py", "", None),
    ],
)
def test_module_name(file: str, root: str, expected: str | None) -> None:
    assert module_name(file, root) == expected


def test_module_name_uses_the_deepest_root(project) -> None:
    root = project({"src/shop/cart.py": "", "src/other.py": "", "tools/t.py": "", "top.py": ""})
    loaded = Project.load(root, ["src/shop"])
    assert loaded.module_name("src/shop/cart.py") == "cart"
    assert loaded.module_name("src/other.py") == "other"
    assert loaded.module_name("tools/t.py") == "tools.t"
    assert loaded.module_name("top.py") == "top"


@pytest.mark.skipif(os.name == "nt", reason="POSIX file names are bytes")
def test_file_names_that_are_not_utf8_are_read_as_windows_1252(tmp_path) -> None:
    try:
        (tmp_path / os.fsdecode(b"caf\xe9.py")).write_text("")
    except OSError:
        pytest.skip("the filesystem only takes UTF-8 names")
    loaded = Project.load(str(tmp_path))
    assert loaded.files == ["café.py"]
    assert os.path.exists(loaded.path("café.py"))
