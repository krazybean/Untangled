# SPDX-License-Identifier: GPL-2.0-only
"""Which distribution an import belongs to: installed ones from the project's
virtualenvs, then declared ones by name (spec/languages/python.md, "Packages")."""

import csv
import glob
import os
import re
from email.parser import HeaderParser
from typing import Any

from untangled.diagnostics import Diagnostic

_REQUIREMENT_NAME = re.compile(r"\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)")
_NATIVE_SUFFIXES = (".so", ".pyd")


def normalize(name: str) -> str:
    """A distribution name as PyPI compares it (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


class PackageIndex:
    def __init__(self, installed: dict[str, set[str]] | None = None, declared: set[str] | None = None) -> None:
        self.installed = installed or {}
        """Dotted module prefix => normalized names of the distributions that install it."""
        self.declared = declared or set()
        """Normalized names of declared dependencies."""

    def package_for(self, dotted: str) -> str | None:
        parts = dotted.split(".")
        for length in range(len(parts), 0, -1):
            names = self.installed.get(".".join(parts[:length]))
            if names:
                return next(iter(names)) if len(names) == 1 else None
        # A declared name matches a dotted prefix, longest first, so `import jaraco.abode`
        # is the jaraco.abode distribution (a namespace package) and `import yaml` is not pyyaml.
        for length in range(len(parts), 0, -1):
            name = normalize(".".join(parts[:length]))
            if name in self.declared:
                return name
        return None

    @classmethod
    def load(
        cls, root: str, venvs: list[str], pyproject: dict[str, Any], diagnostics: list[Diagnostic]
    ) -> "PackageIndex":
        installed: dict[str, set[str]] = {}
        for venv in venvs:
            folder = os.path.join(root, venv)
            site_packages = sorted(
                glob.glob(os.path.join(glob.escape(folder), "lib", "python*", "site-packages"))
                + glob.glob(os.path.join(glob.escape(folder), "Lib", "site-packages"))
            )
            if not site_packages:
                diagnostics.append(
                    Diagnostic.warning(
                        "venv-without-site-packages",
                        f"{venv}: a virtualenv without a site-packages folder; its packages are not read",
                        [venv],
                    )
                )
            for packages in site_packages:
                _read_site_packages(packages, installed)
        return cls(installed, _declared(root, pyproject))


def _read_site_packages(folder: str, installed: dict[str, set[str]]) -> None:
    for entry in sorted(os.listdir(folder)):
        path = os.path.join(folder, entry)
        if entry.endswith(".dist-info"):
            name = _metadata_name(os.path.join(path, "METADATA"))
            modules = _record_modules(os.path.join(path, "RECORD"))
        elif entry.endswith(".egg-info"):
            name = _metadata_name(os.path.join(path, "PKG-INFO") if os.path.isdir(path) else path)
            modules = _top_level_modules(os.path.join(path, "top_level.txt"))
        else:
            continue
        if name is None:
            continue
        for module in modules:
            installed.setdefault(module, set()).add(normalize(name))


def _metadata_name(file: str) -> str | None:
    try:
        with open(file, encoding="utf-8", errors="replace") as handle:
            name = HeaderParser().parse(handle, headersonly=True).get("Name")
    except OSError:
        return None
    return name.strip() if isinstance(name, str) and name.strip() else None


def _record_modules(file: str) -> set[str]:
    """Every dotted module prefix the files of a RECORD install."""
    modules: set[str] = set()
    try:
        with open(file, encoding="utf-8", errors="replace", newline="") as handle:
            rows = list(csv.reader(handle))
    except OSError:
        return modules
    for row in rows:
        if not row:
            continue
        parts = row[0].replace("\\", "/").split("/")
        if parts[0] in ("", "..") or parts[0].endswith((".dist-info", ".data")):
            continue
        last = parts[-1]
        if last.endswith(".py"):
            parts[-1] = last[: -len(".py")]
        elif last.endswith(_NATIVE_SUFFIXES):
            parts[-1] = last.split(".")[0]
        else:
            parts.pop()  # a data file: only its folders are modules
        if parts and parts[-1] == "__init__":
            parts.pop()
        prefix: list[str] = []
        for part in parts:
            if not part.isidentifier():
                break
            prefix.append(part)
            modules.add(".".join(prefix))
    return modules


def _top_level_modules(file: str) -> set[str]:
    try:
        with open(file, encoding="utf-8", errors="replace") as handle:
            return {line.strip() for line in handle if line.strip().isidentifier()}
    except OSError:
        return set()


def _declared(root: str, pyproject: dict[str, Any]) -> set[str]:
    requirements: list[str] = []
    project = _dict(pyproject.get("project"))
    requirements += _strings(project.get("dependencies"))
    for group in _dict(project.get("optional-dependencies")).values():
        requirements += _strings(group)
    for group in _dict(pyproject.get("dependency-groups")).values():
        requirements += _strings(group)  # {include-group = ...} entries are not strings
    names = {normalize(match.group(1)) for item in requirements if (match := _REQUIREMENT_NAME.match(item))}

    poetry = _dict(_dict(pyproject.get("tool")).get("poetry"))
    tables = [poetry.get("dependencies"), poetry.get("dev-dependencies")]
    tables += [_dict(group).get("dependencies") for group in _dict(poetry.get("group")).values()]
    for table in tables:
        names |= {normalize(name) for name in _dict(table) if name.lower() != "python"}

    for file in sorted(glob.glob(os.path.join(glob.escape(root), "requirements*.txt"))):
        try:
            with open(file, encoding="utf-8", errors="replace") as handle:
                lines = handle.read().splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if line.startswith(("#", "-")):
                continue
            match = _REQUIREMENT_NAME.match(line)
            if match:
                names.add(normalize(match.group(1)))
    return names


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _strings(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []
