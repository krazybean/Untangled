# SPDX-License-Identifier: GPL-2.0-only
"""Scans a Python project into a pairs document, following spec/languages/python.md:
every import resolves to a project file, a builtin, a PyPI distribution, an
unresolved node, or (for a namespace package) nothing."""

import os
from collections import deque
from dataclasses import dataclass, field

from untangled.graph import BUILTIN, EXTERNAL, INTERNAL, UNRESOLVED, PairsDocument
from untangled.scanner import imports
from untangled.scanner.packages import PackageIndex
from untangled.scanner.project import Project, module_name
from untangled.scanner.stdlib import is_stdlib

RELATIVE = "relative"

_NAMESPACE = object()
"""lookup() result for a project namespace package: a module with no file."""


@dataclass
class ScanResult:
    pairs: PairsDocument
    warnings: list[str] = field(default_factory=list)


class Scanner:
    def __init__(self, dev: bool = False, sources: list[str] | None = None, venvs: list[str] | None = None) -> None:
        self.dev = dev
        self.sources = sources or []
        self.venvs = venvs

    def scan(self, path: str) -> ScanResult:
        project = Project.load(path, self.sources)
        warnings = list(project.warnings)
        venvs = project.venvs if self.venvs is None else self.venvs
        for venv in self.venvs or []:
            if not os.path.isdir(os.path.join(project.root, venv)):
                warnings.append(f"--venv={venv}: no such folder")
        existing = [venv for venv in venvs if os.path.isdir(os.path.join(project.root, venv))]
        packages = PackageIndex.load(project.root, existing, project.pyproject, warnings)
        resolver = _Resolver(project, packages)

        # Scan the default files, then any test file a scanned file imports.
        results: dict[str, imports.FileImports] = {}
        targets: dict[str, list[tuple[str, list[str]]]] = {}
        queue = deque(file for file in project.files if self.dev or file not in project.tests)
        while queue:
            file = queue.popleft()
            if file in results:
                continue
            try:
                with open(project.path(file), "rb") as handle:
                    result = imports.collect(handle.read())
            except OSError as error:
                result = imports.FileImports(error=f"cannot read it: {error.strerror}")
            results[file] = result
            if result.error is not None:
                warnings.append(f"{file}: {result.error}")
            targets[file] = []
            for item in result.imports:
                for target in resolver.resolve(file, item):
                    if target is None:
                        continue
                    kinds = [item.kind, *sorted(item.contexts)] + ([RELATIVE] if item.level else [])
                    targets[file].append((target, kinds))
                    if project.has_file(target) and target not in results:
                        queue.append(target)

        pairs = PairsDocument("python")
        for file in sorted(results):
            name = project.module_name(file)
            pairs.add_node(file, INTERNAL, **({"module": name} if name is not None else {}))
        for file in sorted(results):
            for target, kinds in targets[file]:
                if not pairs.has_node(target):
                    prefix = target.split(":", 1)[0]
                    pairs.add_node(target, {"builtin": BUILTIN, "pypi": EXTERNAL, "unresolved": UNRESOLVED}[prefix])
                pairs.add_edge(file, target, kinds)

        outside = sorted(
            {name.split(".")[0] for name in resolver.outside if pairs.has_node(f"unresolved:module:{name}")}
        )
        if not venvs and outside:
            named = ", ".join(outside[:5]) + (f" and {len(outside) - 5} more" if len(outside) > 5 else "")
            warnings.append(
                f"no virtualenv found (a folder with pyvenv.cfg, or --venv=<path>), so imports of {named} could only be"
                " matched against declared dependencies by name, and show as unresolved; create the project's"
                " virtualenv first for a complete picture"
            )
        return ScanResult(pairs, warnings)


class _Resolver:
    def __init__(self, project: Project, packages: PackageIndex) -> None:
        self.project = project
        self.packages = packages
        # Every module name a file has under any import root; roots earlier in the
        # list win, and within a root a package's __init__.py wins over a module file.
        self.modules: dict[str, str] = {}
        self.namespaces: set[str] = set()
        packages_first = sorted(project.files, key=lambda file: not file.endswith("/__init__.py"))
        for root in project.roots:
            for file in packages_first:
                if root and not file.startswith(root + "/"):
                    continue
                name = module_name(file, root)
                if name is not None:
                    self.modules.setdefault(name, file)
                    parts = name.split(".")
                    self.namespaces.update(".".join(parts[:i]) for i in range(1, len(parts)))
        self.namespaces -= set(self.modules)
        self._names: dict[str, str | None] = {}
        self.outside: set[str] = set()
        """Unresolved names whose top-level module is not in the project: likely third-party."""

    def resolve(self, file: str, item: imports.Import) -> list[str | None]:
        """One target per reference: per imported name for a `from` import."""
        if item.kind == imports.DYNAMIC and item.module is None:
            return [f"unresolved:dynamic:{item.text}"]
        base = item.module
        if item.level:
            base = self.absolute(file, item.level, item.module)
            if base is None:
                # As written: `..m` for `from ..m import x`, `..x` for `from .. import x`.
                dots = "." * item.level
                if item.module:
                    return [f"unresolved:module:{dots}{item.module}"] * len(item.names)
                return [f"unresolved:module:{dots}{'' if name == '*' else name}" for name in item.names]
        assert base is not None
        if item.kind != imports.FROM:
            return [self.resolve_name(base)]
        return [self.resolve_from(base, name) for name in item.names]

    def absolute(self, file: str, level: int, module: str | None) -> str | None:
        name = self.project.module_name(file)
        if name is None:
            return None
        package = name.split(".") if file.endswith("/__init__.py") else name.split(".")[:-1]
        if level - 1 >= len(package):
            return None
        parts = package[: len(package) - (level - 1)]
        return ".".join(parts + ([module] if module else []))

    def lookup(self, dotted: str) -> str | object | None:
        if dotted in self.modules:
            return self.modules[dotted]
        return _NAMESPACE if dotted in self.namespaces else None

    def resolve_name(self, dotted: str) -> str | None:
        if dotted not in self._names:
            self._names[dotted] = self._resolve_name(dotted)
        return self._names[dotted]

    def _resolve_name(self, dotted: str) -> str | None:
        found = self.lookup(dotted)
        if isinstance(found, str):
            return found
        top = dotted.split(".")[0]
        if found is None and isinstance(self.lookup(top), str):
            return f"unresolved:module:{dotted}"
        if is_stdlib(top):
            return f"builtin:{top}"
        package = self.packages.package_for(dotted)
        if package is not None:
            return f"pypi:{package}"
        if found is _NAMESPACE:
            return None
        if self.lookup(top) is None:
            self.outside.add(dotted)
        return f"unresolved:module:{dotted}"

    def resolve_from(self, base: str, name: str) -> str | None:
        found = None
        if name != "*":
            found = self.lookup(f"{base}.{name}")
            if isinstance(found, str):
                return found
        module = self.lookup(base)
        if isinstance(module, str):
            return module
        if found is _NAMESPACE:
            return None
        target = self.resolve_name(base)
        if target is None and name != "*":
            # base is a namespace package, which has no attributes but its submodules.
            return f"unresolved:module:{base}.{name}"
        return target
