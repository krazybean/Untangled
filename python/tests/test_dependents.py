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
