# SPDX-License-Identifier: GPL-2.0-only
import pytest
from builders import arrows, build, ids

from untangled.analysis.filtering import Filter, Glob
from untangled.graph import CLUSTER, INTERNAL, PairsDocument


def test_drops_builtins_by_default() -> None:
    filtered = Filter().apply(build(["a.py -> builtin:os", "a.py -> b.py"]))
    assert ids(filtered) == ["a.py", "b.py"]
    assert arrows(filtered) == ["a.py>b.py"]


def test_can_keep_builtins() -> None:
    filtered = Filter(keep_builtins=True).apply(build(["a.py -> builtin:os"]))
    assert ids(filtered) == ["a.py", "builtin:os"]


def test_keeps_external_and_unresolved_targets() -> None:
    filtered = Filter().apply(build(["a.py -> pypi:requests", "a.py -> unresolved:module:z"]))
    assert ids(filtered) == ["a.py", "pypi:requests", "unresolved:module:z"]


def test_exclude_removes_files_and_their_edges_both_ways() -> None:
    filtered = (
        Filter()
        .exclude("tests/**")
        .apply(build(["tests/test_a.py -> src/a.py", "src/a.py -> tests/fixture.py", "src/a.py -> src/b.py"]))
    )
    assert ids(filtered) == ["src/a.py", "src/b.py"]
    assert arrows(filtered) == ["src/a.py>src/b.py"]


def test_the_last_matching_pattern_wins() -> None:
    document = build([], isolated=["tests/test_a.py", "tests/keep.py", "src/a.py"])
    assert ids(Filter().exclude("tests/**").include("tests/keep.py").apply(document)) == ["src/a.py", "tests/keep.py"]
    assert ids(Filter().include("tests/keep.py").exclude("tests/**").apply(document)) == ["src/a.py"]


def test_a_file_matching_no_pattern_is_included() -> None:
    document = build([], isolated=["src/a.py", "lib/b.py"])
    assert ids(Filter().include("src/**").apply(document)) == ["lib/b.py", "src/a.py"]


def test_keeps() -> None:
    selection = Filter().exclude("**/test_*.py").include("src/test_keep*.py")
    assert selection.keeps("src/a.py")
    assert not selection.keeps("src/test_a.py")
    assert selection.keeps("src/test_keep_me.py")


def test_drops_targets_that_only_removed_files_used() -> None:
    filtered = (
        Filter()
        .exclude("legacy/**")
        .apply(
            build(
                ["legacy/old.py -> pypi:oldlib", "legacy/old.py -> unresolved:module:gone", "src/a.py -> pypi:newlib"]
            )
        )
    )
    assert ids(filtered) == ["pypi:newlib", "src/a.py"]


def test_keeps_edge_kinds_counts_and_node_fields() -> None:
    document = PairsDocument("python")
    document.add_node("a.py", INTERNAL, module="a", symbols=["a.A"])
    document.add_node("b.py", INTERNAL)
    document.add_edge("a.py", "b.py", ["import"])
    document.add_edge("a.py", "b.py", ["from"], 2)
    assert Filter().apply(document).to_dict() == document.to_dict()


def test_cluster_nodes_pass_through() -> None:
    document = PairsDocument("python")
    document.add_node("app", CLUSTER, members=["a.py"])
    assert Filter().exclude("**").apply(document).has_node("app")


def test_leaves_the_input_untouched() -> None:
    document = build(["a.py -> builtin:os"])
    before = document.to_dict()
    Filter().exclude("a.py").apply(document)
    assert document.to_dict() == before


@pytest.mark.parametrize(
    ("pattern", "node_id", "expected"),
    [
        pytest.param("src/a.py", "src/a.py", True, id="literal"),
        pytest.param("src/a.py", "lib/src/a.py", False, id="matches the whole id"),
        pytest.param("src", "src/a.py", False, id="no prefix match"),
        pytest.param("src/*.py", "src/a.py", True, id="* within a segment"),
        pytest.param("src/*.py", "src/b/a.py", False, id="* does not cross /"),
        pytest.param("src/*a.py", "src/a.py", True, id="* matches empty"),
        pytest.param("src/?.py", "src/a.py", True, id="? one character"),
        pytest.param("src/?.py", "src/ab.py", False, id="? not two"),
        pytest.param("src?a.py", "src/a.py", False, id="? not /"),
        pytest.param("src/**", "src/b/c/a.py", True, id="** crosses /"),
        pytest.param("src/**", "src", False, id="** at the end needs something"),
        pytest.param("**/test_*.py", "test_a.py", True, id="**/ matches no directory"),
        pytest.param("**/test_*.py", "a/b/c/test_a.py", True, id="**/ matches many directories"),
        pytest.param("src/**/legacy/*.py", "src/legacy/a.py", True, id="**/ in the middle"),
        pytest.param("src/**/legacy/*.py", "src/a/b/legacy/a.py", True, id="**/ in the middle, nested"),
        pytest.param("src/**/legacy/*.py", "src/a/legacy/b/a.py", False, id="**/ in the middle, not under it"),
        pytest.param("src/a.py", "src/aXpy", False, id="dot is literal"),
        pytest.param("src/a+b.py", "src/a+b.py", True, id="plus is literal"),
        pytest.param("src/a+b.py", "src/aab.py", False, id="plus is not a quantifier"),
        pytest.param("src/[ab].py", "src/[ab].py", True, id="brackets are literal"),
        pytest.param("src/[ab].py", "src/a.py", False, id="brackets are not a class"),
        pytest.param("src/#.py", "src/#.py", True, id="hash is literal"),
        pytest.param("src/a.py", "src/A.py", False, id="case-sensitive"),
        pytest.param("src/*", "src/a\nb", True, id="newline in id"),
    ],
)
def test_glob(pattern: str, node_id: str, expected: bool) -> None:
    assert Glob(pattern).matches(node_id) is expected
