# SPDX-License-Identifier: GPL-2.0-only
"""Cycles as defined in spec/metrics.md: strongly connected components with two or more units,
each with one concrete example loop."""

from collections import deque
from typing import Any


def find(successors: dict[str, list[str]]) -> list[dict[str, Any]]:
    """`successors` has every unit as a key, with the units it depends on."""
    graph = {unit: sorted(set(targets)) for unit, targets in sorted(successors.items())}
    cycles = []
    for component in _components(graph):
        if len(component) < 2:
            continue
        members = sorted(component)
        cycles.append({"members": members, "size": len(members), "example": _example(members[0], set(members), graph)})
    cycles.sort(key=lambda cycle: (-cycle["size"], cycle["members"][0]))
    return cycles


def _components(graph: dict[str, list[str]]) -> list[list[str]]:
    """Tarjan's algorithm, written iteratively so deep dependency chains cannot overflow the stack."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components = []
    for root in graph:
        if root in index:
            continue
        # Each frame is [unit, position of the next successor to visit].
        frames = [[root, 0]]
        index[root] = low[root] = len(index)
        stack.append(root)
        on_stack.add(root)
        while frames:
            unit, position = frames[-1]
            targets = graph[unit]
            if position < len(targets):
                frames[-1][1] += 1
                target = targets[position]
                if target not in index:
                    index[target] = low[target] = len(index)
                    stack.append(target)
                    on_stack.add(target)
                    frames.append([target, 0])
                elif target in on_stack:
                    low[unit] = min(low[unit], index[target])
                continue
            frames.pop()
            if frames:
                parent = frames[-1][0]
                low[parent] = min(low[parent], low[unit])
            if low[unit] == index[unit]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == unit:
                        break
                components.append(component)
    return components


def _example(start: str, members: set[str], graph: dict[str, list[str]]) -> list[str]:
    """The shortest loop from start back to itself, by breadth-first search visiting
    neighbours in byte order. Any such loop stays inside the cycle, so the search does too."""
    parent: dict[str, str] = {}
    queue = deque([start])
    while queue:
        unit = queue.popleft()
        for target in graph[unit]:
            if target not in members:
                continue
            if target == start:
                path = [start]
                step = unit
                while step != start:
                    path.append(step)
                    step = parent[step]
                path.append(start)
                return path[::-1]
            if target not in parent:
                parent[target] = unit
                queue.append(target)
    raise AssertionError(f"no loop through {start}")
