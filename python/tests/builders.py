# SPDX-License-Identifier: GPL-2.0-only
"""Builds small pairs documents from "from -> to" strings, for analysis and report tests."""

from untangled.graph import BUILTIN, EXTERNAL, INTERNAL, UNRESOLVED, PairsDocument

_PREFIXES = {"pypi:": EXTERNAL, "composer:": EXTERNAL, "builtin:": BUILTIN, "unresolved:": UNRESOLVED}


def build(
    edges: list[str],
    modules: dict[str, str] | None = None,
    isolated: list[str] | None = None,
    language: str = "python",
) -> PairsDocument:
    """Internal nodes are ids without a prefix; `pypi:` (or `composer:`), `builtin:` and
    `unresolved:` ids get their kind from the prefix. `modules` maps internal ids to their
    module, and `isolated` lists internal ids with no edges."""
    modules = modules or {}
    document = PairsDocument(language)

    def add(node_id: str) -> None:
        kind = next((kind for prefix, kind in _PREFIXES.items() if node_id.startswith(prefix)), INTERNAL)
        if node_id in modules:
            document.add_node(node_id, kind, module=modules[node_id])
        else:
            document.add_node(node_id, kind)

    for node_id in isolated or []:
        add(node_id)
    for edge in edges:
        source, target = (part.strip() for part in edge.split("->"))
        add(source)
        add(target)
        document.add_edge(source, target, ["import"])
    return document


def demo() -> PairsDocument:
    """a and b depend on each other, b uses c; a and c use a package; c has a hostile unresolved name."""
    return build(
        [
            "a.py -> b.py",
            "b.py -> a.py",
            "b.py -> c.py",
            "a.py -> pypi:x",
            "c.py -> pypi:x",
            "c.py -> unresolved:module:</script><b>x",
        ]
    )


def ids(document: PairsDocument) -> list[str]:
    return [node["id"] for node in document.nodes()]


def arrows(document: PairsDocument) -> list[str]:
    """Edges as "from>to" strings."""
    return [f"{edge['from']}>{edge['to']}" for edge in document.edges()]
