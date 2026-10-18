# SPDX-License-Identifier: GPL-2.0-only
"""Computes the analysis document of spec/metrics.md from a filtered file-level pairs document:
per-unit coupling, Ca / Ce for clusters, cycles, and the project summary."""

from typing import Any

from untangled import version
from untangled.analysis import cycles as cycle_finder
from untangled.analysis.clustering import Clustering
from untangled.graph import CLUSTER, EXTERNAL, INTERNAL, UNRESOLVED, PairsDocument, number


def analyze(files: PairsDocument, clustering: Clustering | None = None) -> dict[str, Any]:
    """Raises ValueError when the document is already clustered."""
    if any(node["kind"] == CLUSTER for node in files.nodes()):
        raise ValueError(
            "the pairs document is already clustered; analyze the file-level document and choose a clustering instead"
        )
    graph = files
    cluster_of = None
    if clustering is not None:
        clustered = clustering.apply(files)
        graph, cluster_of = clustered.document, clustered.cluster_of

    unit_kind = INTERNAL if clustering is None else CLUSTER
    successors: dict[str, list[str]] = {}
    predecessors: dict[str, list[str]] = {}
    external: dict[str, set[str]] = {}
    unresolved: dict[str, set[str]] = {}
    members: dict[str, list[str]] = {}
    for node in graph.nodes():
        if node["kind"] == unit_kind:
            successors[node["id"]] = []
            predecessors[node["id"]] = []
            external[node["id"]] = set()
            unresolved[node["id"]] = set()
            members[node["id"]] = node.get("members", [])

    edges = 0
    external_used: set[str] = set()
    unresolved_used: set[str] = set()
    for edge in graph.edges():
        source, target = edge["from"], edge["to"]
        kind = (graph.node(target) or {}).get("kind")
        if kind == unit_kind:
            successors[source].append(target)
            predecessors[target].append(source)
            edges += 1
        elif kind == EXTERNAL:
            external[source].add(target)
            external_used.add(target)
        elif kind == UNRESOLVED:
            unresolved[source].add(target)
            unresolved_used.add(target)

    # Ca / Ce of a cluster count the distinct files outside it, on the file graph.
    ca: dict[str, set[str]] = {}
    ce: dict[str, set[str]] = {}
    if cluster_of is not None:
        for edge in files.edges():
            source, target = cluster_of.get(edge["from"]), cluster_of.get(edge["to"])
            if source is None or target is None or source == target:
                continue
            ce.setdefault(source, set()).add(edge["to"])
            ca.setdefault(target, set()).add(edge["from"])

    units = []
    fan_out_total = 0
    for unit_id, targets in successors.items():
        fan_in, fan_out = len(predecessors[unit_id]), len(targets)
        fan_out_total += fan_out
        unit: dict[str, Any] = {"id": unit_id, "fan_in": fan_in, "fan_out": fan_out}
        if cluster_of is not None:
            unit["ca"], unit["ce"] = len(ca.get(unit_id, ())), len(ce.get(unit_id, ()))
            afferent, efferent = unit["ca"], unit["ce"]
        else:
            afferent, efferent = fan_in, fan_out
        unit["external"] = len(external[unit_id])
        unit["unresolved"] = len(unresolved[unit_id])
        unit["instability"] = None if afferent + efferent == 0 else number(efferent / (afferent + efferent))
        if cluster_of is not None:
            unit["members"] = members[unit_id]
        units.append(unit)
    units.sort(key=lambda unit: unit["id"])

    cycles = cycle_finder.find(successors)
    in_cycles = sum(cycle["size"] for cycle in cycles)
    count = len(units)
    return {
        "format": "untangled-analysis",
        "version": version.SPEC,
        "language": files.language,
        "generator": {"name": version.NAME, "version": version.VERSION},
        "clustering": None if clustering is None else clustering.name(),
        "summary": {
            "units": count,
            "edges": edges,
            "cycles": len(cycles),
            "largest_cycle": cycles[0]["size"] if cycles else 0,
            "units_in_cycles": in_cycles,
            "units_in_cycles_ratio": number(in_cycles / count) if count else 0,
            "mean_fan_out": number(fan_out_total / count) if count else 0,
            "external_packages": len(external_used),
            "unresolved_references": len(unresolved_used),
        },
        "units": units,
        "cycles": cycles,
    }
