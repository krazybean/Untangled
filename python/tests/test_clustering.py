# SPDX-License-Identifier: GPL-2.0-only
import pytest
from builders import build, ids

from untangled.analysis.clustering import Clustering
from untangled.graph import INTERNAL, PairsDocument


def of(clustering: Clustering, node_id: str) -> str:
    return clustering.cluster_of({"id": node_id, "kind": "internal"})


@pytest.mark.parametrize(
    ("strategy", "node_id", "module", "expected"),
    [
        pytest.param("namespace:2", "src/Billing/Tax.php", "App\\Billing\\Tax", "App\\Billing", id="namespace:2"),
        pytest.param("namespace:1", "src/Billing/Tax.php", "App\\Billing", "App", id="namespace:1"),
        pytest.param("namespace:3", "src/Tax.php", "App", "App", id="namespace:N keeps a shorter namespace whole"),
        pytest.param(
            "namespace:2", "src/shop/billing/tax.py", "shop.billing.tax", "shop.billing", id="splits modules on dots"
        ),
        pytest.param("namespace:2", "manage.py", "manage", "manage", id="keeps a shorter module whole"),
        pytest.param("namespace:2", "lib/a/b/x.py", None, "lib/a", id="falls back to folder:N without a module"),
        pytest.param("namespace:2", "lib/a/b/x.py", "", "lib/a", id="falls back for an empty module"),
        pytest.param("namespace:2", "setup.py", None, ".", id="fallback puts root files in ."),
        pytest.param("folder:1", "src/shop/tax.py", "shop.tax", "src", id="folder:1"),
        pytest.param("folder:2", "src/shop/tax.py", None, "src/shop", id="folder:2"),
        pytest.param("folder:3", "src/x.py", None, "src", id="folder:N keeps a shorter directory path"),
        pytest.param("folder:1", "setup.py", None, ".", id="folder:N puts root files in ."),
        pytest.param("folder:1", "lib/x.py", "x", "lib", id="folder:N ignores the module"),
    ],
)
def test_cluster_of(strategy: str, node_id: str, module: str | None, expected: str) -> None:
    node = {"id": node_id, "kind": "internal"} | ({} if module is None else {"module": module})
    assert Clustering.from_string(strategy).cluster_of(node) == expected


def test_names() -> None:
    assert Clustering.from_string("namespace:2").name() == "namespace:2"
    assert Clustering("folder", 10).name() == "folder:10"
    assert Clustering.parse_rules("src/ core").name() == "rules"


@pytest.mark.parametrize(
    "strategy",
    [
        "namespace",
        "namespace:0",
        "namespace:-1",
        "namespace:01",
        "files:2",
        "folder:x",
        "folder:2 ",
        "Folder:2",
        "rules",
        "",
    ],
)
def test_rejects_unknown_strategies(strategy: str) -> None:
    with pytest.raises(ValueError, match="unknown clustering"):
        Clustering.from_string(strategy)


def test_the_unknown_strategy_message() -> None:
    with pytest.raises(ValueError) as error:
        Clustering.from_string("files:2")
    assert str(error.value) == 'unknown clustering "files:2" (use namespace:N, folder:N or rules:<file>)'


@pytest.mark.parametrize("strategy", ["namespace", "folder"])
def test_rejects_depth_zero(strategy: str) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        Clustering(strategy, 0)


def test_rules_first_matching_prefix_wins() -> None:
    rules = Clustering.parse_rules("src/billing/ billing\nsrc/invoice billing\nsrc/ core\n")
    assert of(rules, "src/billing/tax.py") == "billing"
    assert of(rules, "src/invoice_line.py") == "billing"
    assert of(rules, "src/clock.py") == "core"
    assert of(rules, "setup.py") == "setup.py"


def test_rules_order_matters() -> None:
    assert of(Clustering.parse_rules("src/ core\nsrc/billing/ billing\n"), "src/billing/tax.py") == "core"


def test_rules_file_syntax() -> None:
    rules = Clustering.parse_rules(
        "# header\r\n\r\n   src/billing/\t\tbilling   # trailing comment\r\n#src/ ignored\nsrc/ core"
    )
    assert of(rules, "src/billing/tax.py") == "billing"
    assert of(rules, "src/x.py") == "core"


def test_an_empty_rules_file_keeps_every_file_alone() -> None:
    assert of(Clustering.parse_rules("# nothing\n"), "src/x.py") == "src/x.py"


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("src/ core extra\n", id="three fields"),
        pytest.param("src/\n", id="one field"),
        pytest.param("src/ core\nlib/\n", id="error on a later line"),
    ],
)
def test_rejects_malformed_rules(text: str) -> None:
    with pytest.raises(ValueError, match='must be "<prefix> <cluster>"'):
        Clustering.parse_rules(text)


def test_the_rule_error_names_the_line() -> None:
    with pytest.raises(ValueError, match="rules line 3"):
        Clustering.parse_rules("# comment\nsrc/ core\nlib/\n")


def test_apply_merges_edges_per_cluster_and_target() -> None:
    document = build(
        [
            "a/1.py -> a/2.py",
            "a/1.py -> b/1.py",
            "a/2.py -> b/1.py",
            "a/2.py -> b/2.py",
            "a/1.py -> pypi:x",
            "a/2.py -> pypi:x",
            "b/1.py -> unresolved:module:z",
        ]
    )
    clustered = Clustering.from_string("folder:1").apply(document)
    assert clustered.document.edges() == [
        {"from": "a", "to": "b", "kinds": ["import"], "count": 3},
        {"from": "a", "to": "pypi:x", "kinds": ["import"], "count": 2},
        {"from": "b", "to": "unresolved:module:z", "kinds": ["import"], "count": 1},
    ]
    assert clustered.cluster_of == {"a/1.py": "a", "a/2.py": "a", "b/1.py": "b", "b/2.py": "b"}
    assert clustered.dropped == {"a": 1}


def test_apply_makes_cluster_nodes_and_passes_others_through() -> None:
    document = build(["a/2.py -> pypi:x", "a/1.py -> builtin:os"], isolated=["c.py"])
    assert Clustering.from_string("folder:1").apply(document).document.nodes() == [
        {"id": ".", "kind": "cluster", "members": ["c.py"]},
        {"id": "a", "kind": "cluster", "members": ["a/1.py", "a/2.py"]},
        {"id": "builtin:os", "kind": "builtin"},
        {"id": "pypi:x", "kind": "external"},
    ]


def test_apply_unions_kinds() -> None:
    document = PairsDocument("python")
    for node_id in ["a/1.py", "a/2.py", "b/1.py"]:
        document.add_node(node_id, INTERNAL)
    document.add_edge("a/1.py", "b/1.py", ["import"])
    document.add_edge("a/2.py", "b/1.py", ["from"])
    document.add_edge("a/2.py", "b/1.py", ["import"])
    clustered = Clustering.from_string("folder:1").apply(document)
    assert clustered.document.edges() == [{"from": "a", "to": "b", "kinds": ["from", "import"], "count": 3}]


def test_numeric_looking_cluster_ids_stay_strings() -> None:
    clustered = Clustering.parse_rules("src/ 1\nlib/ 2\n").apply(build(["src/a.py -> lib/b.py"]))
    assert ids(clustered.document) == ["1", "2"]
    assert clustered.document.edges()[0]["from"] == "1"
    assert clustered.cluster_of == {"lib/b.py": "2", "src/a.py": "1"}
