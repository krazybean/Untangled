# SPDX-License-Identifier: GPL-2.0-only
from untangled.analysis.cycles import find


def members(cycles: list[dict]) -> list[list[str]]:
    return [cycle["members"] for cycle in cycles]


def test_no_units_no_cycles() -> None:
    assert find({}) == []


def test_an_acyclic_graph_has_no_cycles() -> None:
    assert find({"a": ["b", "c"], "b": ["c"], "c": [], "d": ["a"]}) == []


def test_a_two_unit_loop() -> None:
    assert find({"b": ["a"], "a": ["b"]}) == [{"members": ["a", "b"], "size": 2, "example": ["a", "b", "a"]}]


def test_sorts_by_size_then_first_member() -> None:
    cycles = find(
        {
            "e": ["d"],
            "d": ["e"],
            "a": ["c", "b"],
            "b": ["c"],
            "c": ["a"],
            "x": ["y"],
            "y": [],
            "p": ["q"],
            "q": ["p"],
        }
    )
    assert members(cycles) == [["a", "b", "c"], ["d", "e"], ["p", "q"]]
    assert [cycle["size"] for cycle in cycles] == [3, 2, 2]


def test_first_member_compares_as_text() -> None:
    # Numeric-looking ids must not compare as numbers: "10" sorts before "9".
    cycles = find({"9": ["9b"], "9b": ["9"], "10": ["10b"], "10b": ["10"]})
    assert members(cycles) == [["10", "10b"], ["9", "9b"]]


def test_members_sort_in_byte_order() -> None:
    cycles = find({"b": ["B"], "B": ["_"], "_": ["b"]})
    assert cycles[0]["members"] == ["B", "_", "b"]
    assert cycles[0]["example"] == ["B", "_", "b", "B"]


def test_the_example_is_the_shortest_loop_from_the_smallest_member() -> None:
    # a -> b -> c -> d -> a is the long way round; a -> e -> a is shorter.
    cycles = find({"a": ["b", "e"], "b": ["c"], "c": ["d"], "d": ["a"], "e": ["a"]})
    assert cycles[0]["example"] == ["a", "e", "a"]
    assert cycles[0]["size"] == 5


def test_example_ties_break_in_byte_order() -> None:
    assert find({"a": ["c", "b"], "b": ["a"], "c": ["a"]})[0]["example"] == ["a", "b", "a"]


def test_example_of_a_three_loop_with_ties_at_depth_two() -> None:
    # Two loops of length 3: a -> b -> d -> a and a -> c -> d -> a. The search reaches d through b first.
    assert find({"a": ["c", "b"], "b": ["d"], "c": ["d"], "d": ["a"]})[0]["example"] == ["a", "b", "d", "a"]


def test_the_example_stays_inside_its_cycle() -> None:
    # a reaches x, which is not in the cycle; x leads nowhere back, so it must not appear.
    cycles = find({"a": ["b", "x"], "b": ["a"], "x": ["y"], "y": []})
    assert cycles[0]["example"] == ["a", "b", "a"]
    assert cycles[0]["members"] == ["a", "b"]


def test_two_cycles_joined_one_way_stay_separate() -> None:
    assert members(find({"a": ["b"], "b": ["a", "c"], "c": ["d"], "d": ["c"]})) == [["a", "b"], ["c", "d"]]


def test_two_cycles_joined_both_ways_merge() -> None:
    assert members(find({"a": ["b"], "b": ["a", "c"], "c": ["d"], "d": ["c", "a"]})) == [["a", "b", "c", "d"]]


def test_duplicate_successors_are_ignored() -> None:
    assert find({"a": ["b", "b"], "b": ["a", "a"]})[0]["example"] == ["a", "b", "a"]


def test_a_complete_graph() -> None:
    units = [f"u{i:02d}" for i in range(30)]
    cycles = find({unit: [other for other in units if other != unit] for unit in units})
    assert len(cycles) == 1
    assert cycles[0]["size"] == 30
    assert cycles[0]["example"] == ["u00", "u01", "u00"]


def test_a_long_loop_does_not_recurse_deeply() -> None:
    cycles = find({f"n{i:05d}": [f"n{(i + 1) % 20000:05d}"] for i in range(20000)})
    assert len(cycles) == 1
    assert cycles[0]["size"] == 20000
    assert len(cycles[0]["example"]) == 20001
    assert cycles[0]["example"][0] == "n00000"
    assert cycles[0]["example"][19999] == "n19999"


def test_a_long_chain_has_no_cycles() -> None:
    assert find({f"n{i:05d}": [f"n{i + 1:05d}"] if i < 19999 else [] for i in range(20000)}) == []


def test_the_result_does_not_depend_on_input_order() -> None:
    graph = {"a": ["b"], "b": ["c", "a"], "c": ["a"], "d": ["e"], "e": ["d"], "f": ["a"]}
    reversed_graph = {unit: targets[::-1] for unit, targets in reversed(graph.items())}
    assert find(graph) == find(reversed_graph)
