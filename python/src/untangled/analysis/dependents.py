# SPDX-License-Identifier: GPL-2.0-only
"""The dependents query of spec/dependents.md: which files depend on some nodes, directly or
through other files, read from a file-level pairs document."""

import os
import posixpath
import re
import sys
from collections.abc import Sequence
from typing import Any

from untangled import version
from untangled.analysis.filtering import Filter, Glob
from untangled.graph import CLUSTER, INTERNAL, PairsDocument


class DependentsError(ValueError):
    """A dependents query that cannot be answered, with the diagnostic code of spec/diagnostics.md."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


_ABSOLUTE = re.compile(r"^(?:/|[A-Za-z]:[/\\])")
_DRIVE = re.compile(r"^([A-Za-z]):(?:/|$)")


def find(
    files: PairsDocument,
    targets: list[str],
    transitive: bool,
    selection: Filter | None = None,
    *,
    through: Sequence[str] = (),
    max_depth: int | None = None,
    root: str | None = None,
) -> dict[str, Any]:
    """The dependents document. `selection` keeps only the dependents it keeps once the walk is
    done. When there are `through` globs the walk only goes into files matching one, so nothing is
    found by way of other files; with `transitive`, `max_depth` is the deepest dependents to find.
    `root`, the absolute project folder, lets an absolute path inside it be a target. Raises
    ValueError when the document is clustered, a target matches nothing or is an absolute path
    outside `root`, or `max_depth` is below 1 or given without `transitive`."""
    if max_depth is not None and max_depth < 1:
        raise ValueError("the maximum depth must be a positive integer")
    if max_depth is not None and not transitive:
        raise ValueError("the maximum depth only applies to a transitive search")
    eligible = [Glob(pattern) for pattern in through]
    symbols: dict[str, list[str]] = {}
    for node in files.nodes():
        if node["kind"] == CLUSTER:
            raise DependentsError(
                "the pairs document is already clustered; ask about the file-level document instead",
                "document-clustered",
            )
        if node["kind"] == INTERNAL:
            for symbol in node.get("symbols", []):
                symbols.setdefault(symbol, []).append(node["id"])

    resolved = []
    start: set[str] = set()
    for target in targets:
        nodes = [target] if files.has_node(target) else symbols.get(target, [])
        if not nodes:
            nodes = _respelled(files, target, root)
        if not nodes:
            raise DependentsError(f'no node or symbol "{target}" in the pairs document', "target-not-found")
        resolved.append({"target": target, "nodes": sorted(nodes)})
        start.update(nodes)

    dependents_of: dict[str, list[str]] = {}
    for edge in files.edges():
        dependents_of.setdefault(edge["to"], []).append(edge["from"])

    # Breadth-first from the targets, so the first time a file is reached is its shortest distance.
    # A file the walk may not go into is never reached, so nothing is found by way of it.
    deepest = (max_depth if max_depth is not None else sys.maxsize) if transitive else 1
    depth: dict[str, int] = {}
    frontier = sorted(start)
    level = 1
    while frontier and level <= deepest:
        reached = []
        for node_id in frontier:
            for source in dependents_of.get(node_id, []):
                if (
                    source not in start
                    and source not in depth
                    and (not eligible or any(g.matches(source) for g in eligible))
                ):
                    depth[source] = level
                    reached.append(source)
        frontier = reached
        level += 1

    dependents = [
        {"id": node_id, "depth": node_depth}
        for node_id, node_depth in depth.items()
        if selection is None or selection.keeps(node_id)
    ]
    dependents.sort(key=lambda item: (item["depth"], item["id"]))
    return {
        "format": "untangled-dependents",
        "version": version.SPEC,
        "language": files.language,
        "generator": {"name": version.NAME, "version": version.VERSION},
        "transitive": transitive,
        "targets": resolved,
        "dependents": dependents,
    }


def _respelled(files: PairsDocument, target: str, root: str | None) -> list[str]:
    """The nodes a target names when it is not an id or a symbol as written: a path spelled another
    way. Empty when it names none. Raises ValueError for an absolute path outside the project."""
    path = target
    if root is not None and _ABSOLUTE.match(target):
        relative = _inside_project(target, root)
        if relative is None:
            raise DependentsError(f'"{target}" is outside the project folder {root}', "target-outside-project")
        path = relative
    path = _normalize(path)
    return [path] if path and files.has_node(path) else []


def _normalize(path: str) -> str:
    """Separators as `/`, repeated ones and `.` and `..` segments collapsed, a drive letter in upper case."""
    path = re.sub(r"/+", "/", path.replace("\\", "/"))
    drive = ""
    match = _DRIVE.match(path)
    if match:
        drive = match.group(1).upper() + ":"
        path = "/" + path[2:].lstrip("/")
    normal = posixpath.normpath(path) if path else ""
    if normal == ".":
        normal = ""
    return drive + normal


def _inside_project(path: str, root: str) -> str | None:
    """The project-relative form of an absolute path, or None when it is not inside `root`. Symbolic
    links are resolved on both sides as well, so either spelling of the folder works."""
    roots = {_normalize(root), _normalize(os.path.realpath(root))}
    paths = {_normalize(path), _normalize(os.path.realpath(path))}
    for candidate in sorted(paths):
        for base in sorted(roots):
            base = base.rstrip("/")
            if candidate == base:
                return "."
            if candidate.startswith(base + "/"):
                return candidate[len(base) + 1 :]
    return None


def render_text(document: dict[str, Any]) -> str:
    """The text form for people: a count, then the dependents grouped by folder."""
    targets = ", ".join(item["target"] for item in document["targets"])
    dependents = document["dependents"]
    if not dependents:
        return f"No dependents of {targets}\n"
    folders: dict[str, dict[str, int]] = {}
    for item in dependents:
        folder, slash, name = item["id"].rpartition("/")
        folders.setdefault(f"{folder}/" if slash else "./", {})[name] = item["depth"]
    count = len(dependents)
    text = f"{count} {'dependent' if count == 1 else 'dependents'} of {targets}\n"
    for folder in sorted(folders):
        text += f"\n{folder}\n"
        for name in sorted(folders[folder]):
            suffix = f"  (depth {folders[folder][name]})" if document["transitive"] else ""
            text += f"  {name}{suffix}\n"
    return text
