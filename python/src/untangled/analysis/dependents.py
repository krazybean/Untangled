# SPDX-License-Identifier: GPL-2.0-only
"""The dependents query of spec/dependents.md: which files depend on some nodes, directly or
through other files, read from a file-level pairs document."""

from typing import Any

from untangled import version
from untangled.analysis.filtering import Filter
from untangled.graph import CLUSTER, INTERNAL, PairsDocument


def find(files: PairsDocument, targets: list[str], transitive: bool, selection: Filter | None = None) -> dict[str, Any]:
    """The dependents document. `selection` keeps only the dependents it keeps; the walk itself is
    not filtered. Raises ValueError when the document is clustered or a target matches nothing."""
    symbols: dict[str, list[str]] = {}
    for node in files.nodes():
        if node["kind"] == CLUSTER:
            raise ValueError("the pairs document is already clustered; ask about the file-level document instead")
        if node["kind"] == INTERNAL:
            for symbol in node.get("symbols", []):
                symbols.setdefault(symbol, []).append(node["id"])

    resolved = []
    start: set[str] = set()
    for target in targets:
        nodes = [target] if files.has_node(target) else symbols.get(target, [])
        if not nodes:
            raise ValueError(f'no node or symbol "{target}" in the pairs document')
        resolved.append({"target": target, "nodes": sorted(nodes)})
        start.update(nodes)

    dependents_of: dict[str, list[str]] = {}
    for edge in files.edges():
        dependents_of.setdefault(edge["to"], []).append(edge["from"])

    # Breadth-first from the targets, so the first time a file is reached is its shortest distance.
    depth: dict[str, int] = {}
    frontier = sorted(start)
    level = 1
    while frontier and (transitive or level == 1):
        reached = []
        for node_id in frontier:
            for source in dependents_of.get(node_id, []):
                if source not in start and source not in depth:
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
