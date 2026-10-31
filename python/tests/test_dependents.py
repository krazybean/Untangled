# SPDX-License-Identifier: GPL-2.0-only
import pytest
from builders import build

from untangled.analysis.dependents import find, render_text
from untangled.analysis.filtering import Filter
from untangled.graph import CLUSTER, PairsDocument


def graph() -> PairsDocument:
    """web/controller -> core/service -> core/repo, web/view -> core/service, a cycle
    core/repo <-> core/cache, and web/controller uses pypi:acme."""
    document = build(
        [
            "web/controller.py -> core/service.py",
            "web/view.py -> core/service.py",
            "core/service.py -> core/repo.py",
            "core/repo.py -> core/cache.py",
            "core/cache.py -> core/repo.py",
            "web/controller.py -> pypi:acme",
        ]
    )
    for node_id, symbol in {"core/service.py": "core.service", "web/view.py": "web.view"}.items():
        document.node(node_id)["symbols"] = [symbol]
    return document


def depths(document: dict) -> dict[str, int]:
    return {item["id"]: item["depth"] for item in document["dependents"]}


def test_direct_dependents_by_default() -> None:
    document = find(graph(), ["core/service.py"], False)
    assert depths(document) == {"web/controller.py": 1, "web/view.py": 1}
    assert document["transitive"] is False


def test_transitive_dependents_carry_their_shortest_depth() -> None:
    document = find(graph(), ["core/cache.py"], True)
    assert depths(document) == {"core/repo.py": 1, "core/service.py": 2, "web/controller.py": 3, "web/view.py": 3}


def test_dependents_are_sorted_by_depth_then_id() -> None:
    document = find(graph(), ["core/cache.py"], True)
    assert [item["id"] for item in document["dependents"]] == [
        "core/repo.py",
        "core/service.py",
        "web/controller.py",
        "web/view.py",
    ]


def test_a_target_in_a_cycle_is_not_its_own_dependent() -> None:
    document = find(graph(), ["core/repo.py"], True)
    assert "core/repo.py" not in depths(document)
    assert depths(document)["core/cache.py"] == 1


def test_a_symbol_names_the_file_that_declares_it() -> None:
    document = find(graph(), ["core.service"], False)
    assert document["targets"] == [{"target": "core.service", "nodes": ["core/service.py"]}]
    assert [item["id"] for item in document["dependents"]] == ["web/controller.py", "web/view.py"]


def test_an_external_package_can_be_a_target() -> None:
    assert depths(find(graph(), ["pypi:acme"], True)) == {"web/controller.py": 1}


def test_several_targets_are_one_query_at_the_shortest_distance() -> None:
    document = find(graph(), ["core/repo.py", "core/service.py"], True)
    # service is a target, so it is not listed even though it depends on repo.
    assert depths(document) == {"core/cache.py": 1, "web/controller.py": 1, "web/view.py": 1}
    assert document["targets"][0]["nodes"] == ["core/repo.py"]


def test_a_symbol_declared_in_several_files_matches_all_of_them() -> None:
    document = build(["user.py -> b.py"], isolated=["a.py"])
    for node_id in ("a.py", "b.py"):
        document.node(node_id)["symbols"] = ["polyfill"]
    found = find(document, ["polyfill"], False)
    assert found["targets"][0]["nodes"] == ["a.py", "b.py"]
    assert depths(found) == {"user.py": 1}


def test_the_filter_hides_dependents_but_the_walk_goes_through_them() -> None:
    selection = Filter()
    selection.exclude("**")
    selection.include("web/**")
    assert depths(find(graph(), ["core/cache.py"], True, selection)) == {"web/controller.py": 3, "web/view.py": 3}


def test_nothing_depends_on_a_top_level_file() -> None:
    document = find(graph(), ["web/controller.py"], True)
    assert document["dependents"] == []
    assert render_text(document) == "No dependents of web/controller.py\n"


def test_an_unknown_target_is_an_error() -> None:
    with pytest.raises(ValueError, match='no node or symbol "nope" in the pairs document'):
        find(graph(), ["core/service.py", "nope"], False)


def test_a_clustered_document_is_refused() -> None:
    document = PairsDocument("python")
    document.add_node("core", CLUSTER, members=["a.py"])
    with pytest.raises(ValueError, match="already clustered"):
        find(document, ["core"], False)


def test_text_groups_dependents_by_folder() -> None:
    document = find(graph(), ["core/service.py", "core/repo.py"], False)
    assert render_text(document) == (
        "3 dependents of core/service.py, core/repo.py\n\ncore/\n  cache.py\n\nweb/\n  controller.py\n  view.py\n"
    )


def test_text_shows_the_depth_when_transitive_and_root_files_go_first() -> None:
    document = find(build(["index.py -> lib/a.py", "lib/b.py -> lib/a.py"]), ["lib/a.py"], True)
    assert render_text(document) == "2 dependents of lib/a.py\n\n./\n  index.py  (depth 1)\n\nlib/\n  b.py  (depth 1)\n"


def test_text_counts_one_dependent_in_the_singular() -> None:
    assert render_text(find(build(["a.py -> b.py"]), ["b.py"], False)).startswith("1 dependent of b.py\n")


def test_ids_are_sorted_by_byte_value_even_when_they_look_numeric() -> None:
    document = build(["9 -> t", "10 -> t", "1e1 -> t", "2 -> t"])
    result = find(document, ["t"], False)
    assert [item["id"] for item in result["dependents"]] == ["10", "1e1", "2", "9"]


def test_only_internal_nodes_answer_to_a_symbol() -> None:
    document = build(["a.py -> pypi:y"])
    document.node("pypi:y")["symbols"] = ["vendor.y"]
    with pytest.raises(ValueError, match='no node or symbol "vendor.y"'):
        find(document, ["vendor.y"], False)


def ids(document: dict) -> list[str]:
    return [item["id"] for item in document["dependents"]]


def test_max_depth_stops_the_walk() -> None:
    def found(depth: int) -> dict[str, int]:
        return depths(find(graph(), ["core/cache.py"], True, max_depth=depth))

    assert found(1) == {"core/repo.py": 1}
    assert found(2) == {"core/repo.py": 1, "core/service.py": 2}
    assert found(3) == {"core/repo.py": 1, "core/service.py": 2, "web/controller.py": 3, "web/view.py": 3}
    assert found(1000) == found(3)


def test_max_depth_of_one_is_the_direct_dependents() -> None:
    direct = find(graph(), ["core/service.py"], False)
    limited = find(graph(), ["core/service.py"], True, max_depth=1)
    assert limited["dependents"] == direct["dependents"]
    assert limited["transitive"] is True


def test_max_depth_below_one_is_refused() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        find(graph(), ["core/service.py"], True, max_depth=0)


def test_through_only_goes_into_matching_files() -> None:
    def found(through: list[str], targets: list[str] | None = None) -> dict[str, int]:
        return depths(find(graph(), targets or ["core/cache.py"], True, through=through))

    assert found(["core/**"]) == {"core/repo.py": 1, "core/service.py": 2}
    # Repo is not eligible, so nothing is found by way of it, even the web files that use service.
    assert found(["web/**"]) == {}
    # The patterns are alternatives.
    assert found(["core/**", "web/**"]) == {
        "core/repo.py": 1,
        "core/service.py": 2,
        "web/controller.py": 3,
        "web/view.py": 3,
    }
    # The target is the start of the walk whatever it matches: cache is not in the list.
    assert found(["core/repo.py"]) == {"core/repo.py": 1}


def test_through_finds_the_shortest_path_through_eligible_files_only() -> None:
    # c is two steps from t by way of x, but x is not eligible: by way of m and a it is three.
    document = build(["x.py -> t.py", "c.py -> x.py", "a.py -> t.py", "m.py -> a.py", "c.py -> m.py"])
    assert depths(find(document, ["t.py"], True, through=["a.py", "m.py", "c.py"])) == {
        "a.py": 1,
        "m.py": 2,
        "c.py": 3,
    }
    assert depths(find(document, ["t.py"], True)) == {"a.py": 1, "x.py": 1, "c.py": 2, "m.py": 2}


def test_through_applies_to_direct_dependents_too() -> None:
    assert ids(find(graph(), ["core/service.py"], False, through=["web/controller.py"])) == ["web/controller.py"]


def test_through_combines_with_max_depth_and_the_output_filter() -> None:
    both = ["core/**", "web/**"]
    assert depths(find(graph(), ["core/cache.py"], True, through=both, max_depth=2)) == {
        "core/repo.py": 1,
        "core/service.py": 2,
    }
    # --exclude hides service from the list but the walk still goes through it.
    hidden = Filter()
    hidden.exclude("core/service.py")
    assert depths(find(graph(), ["core/cache.py"], True, hidden, through=both)) == {
        "core/repo.py": 1,
        "web/controller.py": 3,
        "web/view.py": 3,
    }
    # --include cannot bring back a file --through left out.
    everything = Filter()
    everything.include("**")
    assert find(graph(), ["core/cache.py"], True, everything, through=["web/**"])["dependents"] == []


def test_through_with_two_targets_and_a_cycle_lists_each_file_once() -> None:
    document = find(graph(), ["core/repo.py", "core/cache.py"], True, through=["core/**", "web/**"])
    assert depths(document) == {"core/service.py": 1, "web/controller.py": 2, "web/view.py": 2}


@pytest.mark.parametrize(
    ("target", "root"),
    [
        ("core/service.py", "/work/app"),
        ("./core/service.py", "/work/app"),
        ("core\\service.py", "/work/app"),
        ("core//x/../service.py", "/work/app"),
        ("/work/app/core/service.py", "/work/app"),
        ("/work/app/./core/../core/service.py", "/work/app"),
        ("C:\\work\\app\\core\\service.py", "c:/work/app"),
    ],
)
def test_paths_are_respelled_to_project_ids(target: str, root: str) -> None:
    assert find(graph(), [target], False, root=root)["targets"][0]["nodes"] == ["core/service.py"]


@pytest.mark.parametrize(
    "target",
    [
        "/work/other/core/service.py",
        "/work/application/core/service.py",
        "/work/app/../app2/x.py",
        "D:\\work\\app\\core\\service.py",
    ],
)
def test_an_absolute_path_outside_the_project_is_refused(target: str) -> None:
    with pytest.raises(ValueError, match="is outside the project folder /work/app"):
        find(graph(), [target], False, root="/work/app")


def test_an_absolute_path_matches_nothing_without_a_project_folder() -> None:
    with pytest.raises(ValueError, match='no node or symbol "/work/app/core/service.py"'):
        find(graph(), ["/work/app/core/service.py"], False)


def test_an_as_written_match_still_wins_over_a_respelling() -> None:
    document = build(["./a/b.py -> a/b.py"])
    assert find(document, ["./a/b.py"], False)["targets"][0]["nodes"] == ["./a/b.py"]
