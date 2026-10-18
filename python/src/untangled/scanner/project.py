# SPDX-License-Identifier: GPL-2.0-only
"""Which files a Python project has, its import roots, and the module names they give
(spec/languages/python.md, "Input", "Import roots" and "Module names")."""

import keyword
import os
import tomllib
from dataclasses import dataclass, field
from typing import Any

from untangled.text import path_text

_SKIPPED_FOLDERS = {"__pycache__", "node_modules", "site-packages"}
_SKIPPED_AT_ROOT = {"build", "dist"}
_TEST_FOLDERS = {"test", "tests"}
# Modules without Python source, importable but not scanned: stubs, Cython sources and
# compiled extensions, in the order they win when a folder has several for one module.
EXTENSION_SUFFIXES = (".pyi", ".pyx", ".so", ".pyd")


class ProjectError(Exception):
    pass


@dataclass
class Project:
    """A project on disk. File ids are project-relative POSIX paths, as UTF-8 text."""

    root: str
    files: list[str]
    """Every .py file, sorted by id: the ones scanned by default and the tests."""
    tests: set[str]
    roots: list[str]
    """Import roots as project-relative folders ("" is the project root), in resolution order."""
    pyproject: dict[str, Any]
    venvs: list[str] = field(default_factory=list)
    """Folders directly under the root that hold a pyvenv.cfg."""
    extensions: list[str] = field(default_factory=list)
    """Modules without a .py file (see EXTENSION_SUFFIXES), sorted by id: import targets, never scanned."""
    warnings: list[str] = field(default_factory=list)
    _paths: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str, sources: list[str] | None = None) -> "Project":
        if not os.path.isdir(path):
            raise ProjectError(f"{path} is not a folder")
        root = os.path.abspath(path)
        warnings: list[str] = []
        pyproject = _read_pyproject(root, warnings)
        files, tests, venvs, paths, extensions = _walk(root)
        roots: list[str] = []
        for source in sources or []:
            folder = _relative_folder(root, source)
            if folder is None:
                warnings.append(f"--source={source}: outside the project, ignored")
            elif not os.path.isdir(os.path.join(root, folder)):
                warnings.append(f"--source={source}: no such folder in the project")
            else:
                roots.append(folder)
        tool = pyproject.get("tool")
        setuptools = tool.get("setuptools") if isinstance(tool, dict) else None
        setuptools = setuptools if isinstance(setuptools, dict) else {}
        declared = []
        package_dir = setuptools.get("package-dir", {})
        if isinstance(package_dir, dict) and isinstance(package_dir.get(""), str):
            declared.append(package_dir[""])
        find = setuptools.get("packages", {})
        if isinstance(find, dict):
            where = find.get("find", {}).get("where", []) if isinstance(find.get("find"), dict) else []
            declared.extend(item for item in where if isinstance(item, str))
        for item in declared:
            folder = _relative_folder(root, item)
            if folder is not None and os.path.isdir(os.path.join(root, folder)):
                roots.append(folder)
        if os.path.isdir(os.path.join(root, "src")) and not os.path.isfile(os.path.join(root, "src", "__init__.py")):
            roots.append("src")
        roots.append("")
        unique = list(dict.fromkeys(roots))
        return cls(root, files, tests, unique, pyproject, venvs, extensions, warnings, paths)

    def has_file(self, file_id: str) -> bool:
        return file_id in self._paths

    def path(self, file_id: str) -> str:
        """The file's absolute path on disk."""
        return self._paths[file_id]

    def module_name(self, file_id: str) -> str | None:
        """The file's module name, from the import root with the most path segments that holds it."""
        holding = [root for root in self.roots if _under(file_id, root)]
        if not holding:
            return None
        deepest = max(holding, key=lambda root: len(root.split("/")) if root else 0)
        return module_name(file_id, deepest)


def module_name(file_id: str, root: str) -> str | None:
    """The module name of a file relative to one import root, or None when it has none."""
    relative = file_id[len(root) + 1 :] if root else file_id
    folder, _, name = relative.rpartition("/")
    if name.endswith((".so", ".pyd")):
        name = name.split(".")[0]  # _yaml.cpython-313-x86_64-linux-gnu.so is _yaml
    else:
        name = name.rpartition(".")[0]
    parts = (folder.split("/") if folder else []) + [name]
    if parts[-1] == "__init__":
        parts.pop()
    if not parts or not all(part.isidentifier() and not keyword.iskeyword(part) for part in parts):
        return None
    return ".".join(parts)


def is_test_file(name: str) -> bool:
    return name == "conftest.py" or name.startswith("test_") or name.endswith("_test.py")


def _under(file_id: str, root: str) -> bool:
    return not root or file_id.startswith(root + "/")


def _relative_folder(root: str, path: str) -> str | None:
    """A project-relative POSIX folder, "" for the root, or None when outside the project."""
    absolute = os.path.normpath(os.path.join(root, path))
    relative = os.path.relpath(absolute, root)
    if relative == os.curdir:
        return ""
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        return None
    return path_text(relative).replace(os.sep, "/")


def _read_pyproject(root: str, warnings: list[str]) -> dict[str, Any]:
    file = os.path.join(root, "pyproject.toml")
    if not os.path.isfile(file):
        return {}
    try:
        with open(file, "rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        warnings.append(f"pyproject.toml: cannot read it ({error}); ignoring it")
        return {}


def _walk(root: str) -> tuple[list[str], set[str], list[str], dict[str, str], list[str]]:
    paths: dict[str, str] = {}
    extensions: list[str] = []
    tests: set[str] = set()
    venvs: list[str] = []
    for folder, subfolders, names in os.walk(root):
        relative = os.path.relpath(folder, root)
        prefix = "" if relative == os.curdir else path_text(relative).replace(os.sep, "/") + "/"
        in_tests = bool(prefix) and any(part in _TEST_FOLDERS for part in prefix.rstrip("/").split("/"))
        kept = []
        for name in sorted(subfolders):
            full = os.path.join(folder, name)
            if os.path.isfile(os.path.join(full, "pyvenv.cfg")):
                if not prefix:
                    venvs.append(path_text(name))
                continue
            if (
                name.startswith(".")
                or name in _SKIPPED_FOLDERS
                or name.endswith(".egg-info")
                or (not prefix and name in _SKIPPED_AT_ROOT)
                or os.path.islink(full)
            ):
                continue
            kept.append(name)
        subfolders[:] = kept
        for name in names:
            if name.endswith(EXTENSION_SUFFIXES) and os.path.isfile(os.path.join(folder, name)):
                extensions.append(prefix + path_text(name))
            if not name.endswith(".py") or not os.path.isfile(os.path.join(folder, name)):
                continue
            file_id = prefix + path_text(name)
            paths[file_id] = os.path.join(folder, name)
            if in_tests or is_test_file(path_text(name)):
                tests.add(file_id)
    return sorted(paths), tests, venvs, paths, sorted(extensions)
