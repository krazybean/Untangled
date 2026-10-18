# SPDX-License-Identifier: GPL-2.0-only
import pytest
from builders import build

from untangled import version
from untangled.analysis.analyzer import analyze
from untangled.analysis.clustering import Clustering
from untangled.graph import PairsDocument


def by_id(analysis: dict) -> dict[str, dict]:
    return {unit["id"]: unit for unit in analysis["units"]}


def layered() -> PairsDocument:
    """web/ and cli/ use core/; within core/, service uses repo."""
    return build(
        [
            "web/controller.py -> core/service.py",
            "web/controller.py -> core/repo.py",
            "web/view.py -> core/service.py",
            "cli/command.py -> core/service.py",
            "core/service.py -> core/repo.py",
        ]
    )


def test_header() -> None:
    analysis = analyze(PairsDocument("python"))
    assert analysis["format"] == "untangled-analysis"
    assert analysis["version"] == version.SPEC
    assert analysis["language"] == "python"
    assert analysis["generator"] == {"name": version.NAME, "version": version.VERSION}
    assert analysis["clustering"] is None
    assert list(analysis) == ["format", "version", "language", "generator", "clustering", "summary", "units", "cycles"]


def test_empty_project() -> None:
    analysis = analyze(PairsDocument("python"))
    assert analysis["summary"] == {
        "units": 0,
        "edges": 0,
        "cycles": 0,
        "largest_cycle": 0,
        "units_in_cycles": 0,
        "units_in_cycles_ratio": 0,
        "mean_fan_out": 0,
        "external_packages": 0,
        "unresolved_references": 0,
    }
    assert analysis["units"] == []
    assert analysis["cycles"] == []


def test_file_unit_metrics() -> None:
    analysis = analyze(
        build(
            [
                "a.py -> b.py",
                "a.py -> c.py",
                "b.py -> c.py",
                "a.py -> pypi:x",
                "a.py -> pypi:z",
                "b.py -> pypi:x",
                "c.py -> unresolved:module:q",
            ],
            isolated=["d.py"],
        )
    )
    assert analysis["units"] == [
        {"id": "a.py", "fan_in": 0, "fan_out": 2, "external": 2, "unresolved": 0, "instability": 1},
        {"id": "b.py", "fan_in": 1, "fan_out": 1, "external": 1, "unresolved": 0, "instability": 0.5},
        {"id": "c.py", "fan_in": 2, "fan_out": 0, "external": 0, "unresolved": 1, "instability": 0},
        {"id": "d.py", "fan_in": 0, "fan_out": 0, "external": 0, "unresolved": 0, "instability": None},
    ]
    assert list(analysis["units"][0]) == ["id", "fan_in", "fan_out", "external", "unresolved", "instability"]
    # Whole numbers are integers, so they are written without ".0".
    assert type(analysis["units"][0]["instability"]) is int
    assert analysis["summary"] == {
        "units": 4,
        "edges": 3,
        "cycles": 0,
        "largest_cycle": 0,
        "units_in_cycles": 0,
        "units_in_cycles_ratio": 0,
        "mean_fan_out": 0.75,
        "external_packages": 2,
        "unresolved_references": 1,
    }


def test_a_file_with_only_external_dependencies_has_no_instability() -> None:
    unit = analyze(build(["a.py -> pypi:x"]))["units"][0]
    assert unit["instability"] is None
    assert unit["external"] == 1


def test_builtin_nodes_never_count() -> None:
    # The analyzer is normally given a filtered document; a builtin left in still adds nothing.
    analysis = analyze(build(["a.py -> builtin:os"]))
    assert (analysis["summary"]["units"], analysis["summary"]["edges"]) == (1, 0)
    assert analysis["units"][0]["external"] == 0


def test_cycle_summary() -> None:
    analysis = analyze(
        build(["a.py -> b.py", "b.py -> c.py", "c.py -> a.py", "d.py -> e.py", "e.py -> d.py", "f.py -> a.py"])
    )
    summary = analysis["summary"]
    assert (summary["cycles"], summary["largest_cycle"], summary["units_in_cycles"]) == (2, 3, 5)
    assert summary["units_in_cycles_ratio"] == 0.8333
    assert analysis["cycles"][0]["example"] == ["a.py", "b.py", "c.py", "a.py"]


def test_fractions_are_rounded_to_four_places() -> None:
    analysis = analyze(build(["a.py -> b.py", "c.py -> b.py", "b.py -> d.py"]))
    b = analysis["units"][1]
    assert b["id"] == "b.py"
    assert b["instability"] == 0.3333
    assert analysis["summary"]["mean_fan_out"] == 0.75


def test_cluster_units_carry_ca_ce_and_members_in_spec_order() -> None:
    analysis = analyze(layered(), Clustering.from_string("folder:1"))
    assert analysis["clustering"] == "folder:1"
    assert list(analysis["units"][0]) == [
        "id",
        "fan_in",
        "fan_out",
        "ca",
        "ce",
        "external",
        "unresolved",
        "instability",
        "members",
    ]


def test_ca_and_ce_count_files_not_clusters() -> None:
    units = by_id(analyze(layered(), Clustering.from_string("folder:1")))
    # web/ depends on one cluster (core) but on two files in it.
    web = units["web"]
    assert (web["fan_out"], web["ce"], web["ca"], web["instability"]) == (1, 2, 0, 1)
    # core/ is used by two files in web/ and one in cli/, and uses nothing outside.
    core = units["core"]
    assert (core["fan_in"], core["ca"], core["ce"], core["instability"]) == (2, 3, 0, 0)


def test_cluster_instability_uses_ca_and_ce_not_fan_counts() -> None:
    # x/ depends on two files of y/; one file of y/ depends back on x/.
    # Fan counts give 1 / (1 + 1) = 0.5, Ca / Ce give 2 / (1 + 2) = 0.6667.
    document = build(["x/a.py -> y/1.py", "x/a.py -> y/2.py", "y/1.py -> x/a.py"])
    units = by_id(analyze(document, Clustering.from_string("folder:1")))
    assert {key: units["x"][key] for key in ("fan_in", "fan_out", "ca", "ce")} == {
        "fan_in": 1,
        "fan_out": 1,
        "ca": 1,
        "ce": 2,
    }
    assert units["x"]["instability"] == 0.6667
    # y/ is used by one file of x/ and uses that same file: 1 / (1 + 1).
    assert units["y"]["instability"] == 0.5


def test_edges_inside_a_cluster_do_not_count() -> None:
    analysis = analyze(build(["a/1.py -> a/2.py", "a/2.py -> a/1.py"]), Clustering.from_string("folder:1"))
    assert analysis["units"][0] == {
        "id": "a",
        "fan_in": 0,
        "fan_out": 0,
        "ca": 0,
        "ce": 0,
        "external": 0,
        "unresolved": 0,
        "instability": None,
        "members": ["a/1.py", "a/2.py"],
    }
    assert analysis["summary"]["edges"] == 0
    assert analysis["cycles"] == []


def test_clustering_can_reveal_a_cycle() -> None:
    document = build(["a/1.py -> b/1.py", "b/2.py -> a/2.py"])
    assert analyze(document)["cycles"] == []
    assert analyze(document, Clustering.from_string("folder:1"))["cycles"] == [
        {"members": ["a", "b"], "size": 2, "example": ["a", "b", "a"]}
    ]


def test_cluster_external_and_unresolved_are_the_union_of_its_files() -> None:
    document = build(
        [
            "a/1.py -> pypi:x",
            "a/2.py -> pypi:x",
            "a/2.py -> pypi:z",
            "a/1.py -> unresolved:module:q",
            "a/2.py -> unresolved:module:q",
        ]
    )
    unit = analyze(document, Clustering.from_string("folder:1"))["units"][0]
    assert (unit["external"], unit["unresolved"]) == (2, 1)


def test_namespace_clustering_falls_back_to_folders() -> None:
    document = build(["src/app/domain/sub.py -> setup.py"], modules={"src/app/domain/sub.py": "app.domain.sub"})
    analysis = analyze(document, Clustering.from_string("namespace:2"))
    assert [unit["id"] for unit in analysis["units"]] == [".", "app.domain"]


def test_refuses_an_already_clustered_document() -> None:
    clustered = Clustering.from_string("folder:1").apply(build(["a/1.py -> b/1.py"])).document
    with pytest.raises(ValueError, match="already clustered"):
        analyze(clustered)


def test_the_result_does_not_depend_on_insertion_order() -> None:
    edges = ["c.py -> a.py", "a.py -> b.py", "b.py -> a.py", "b.py -> pypi:x", "d.py -> c.py"]
    assert analyze(build(edges)) == analyze(build(edges[::-1]))
