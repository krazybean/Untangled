# SPDX-License-Identifier: GPL-2.0-only
from untangled.scanner.packages import PackageIndex, normalize

SITE = ".venv/lib/python3.12/site-packages/"


def dist(name: str, record: list[str], folder: str | None = None) -> dict[str, str]:
    folder = folder or f"{name.replace('-', '_')}-1.0.dist-info"
    return {
        SITE + folder + "/METADATA": f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n",
        SITE + folder + "/RECORD": "".join(f"{path},sha256=x,1\n" for path in record),
    }


def load(root: str, venvs: list[str] | None = None, pyproject: dict | None = None) -> tuple[PackageIndex, list[str]]:
    warnings: list[str] = []
    return PackageIndex.load(root, [".venv"] if venvs is None else venvs, pyproject or {}, warnings), warnings


def test_normalize() -> None:
    assert normalize("PyYAML") == "pyyaml"
    assert normalize("typing_extensions") == "typing-extensions"
    assert normalize("zope.interface") == "zope-interface"
    assert normalize("A__b--c") == "a-b-c"


def test_record_gives_every_module_and_package_level(project) -> None:
    root = project(
        dist(
            "PyYAML",
            [
                "yaml/__init__.py",
                "yaml/loader.py",
                "_yaml/__init__.py",
                "yaml/_ext.cpython-312-x86_64-linux-gnu.so",
                "six.py",
                "native.cp312-win_amd64.pyd",
                "PyYAML-1.0.dist-info/METADATA",
                "PyYAML-1.0.data/scripts/tool",
                "../../../bin/yaml-tool",
                "yaml/data/schema.json",
                "yaml/not-a-module/x.py",
                "",
            ],
            folder="PyYAML-1.0.dist-info",
        )
    )
    index, _ = load(root)
    assert set(index.installed) == {"yaml", "yaml.loader", "_yaml", "yaml._ext", "six", "native", "yaml.data"}
    assert index.package_for("yaml.loader") == "pyyaml"
    assert index.package_for("six") == "pyyaml"


def test_the_longest_installed_prefix_decides(project) -> None:
    root = project(
        {
            **dist("google-auth", ["google/auth/__init__.py", "google/auth/jwt.py"]),
            **dist("protobuf", ["google/protobuf/__init__.py"]),
        }
    )
    index, _ = load(root)
    assert index.package_for("google.auth.jwt") == "google-auth"
    assert index.package_for("google.auth.missing") == "google-auth"
    assert index.package_for("google.protobuf.message") == "protobuf"
    assert index.package_for("google") is None
    assert index.package_for("google.cloud") is None


def test_egg_info_uses_top_level_txt(project) -> None:
    root = project(
        {
            SITE + "old-1.0.egg-info/PKG-INFO": "Metadata-Version: 1.1\nName: Old_Thing\n",
            SITE + "old-1.0.egg-info/top_level.txt": "old\nold_helpers\n\n",
            SITE + "single-2.0.egg-info": "Metadata-Version: 1.1\nName: single\n",
        }
    )
    index, _ = load(root)
    assert index.package_for("old_helpers.x") == "old-thing"
    assert index.package_for("single") is None


def test_dist_info_without_a_name_is_skipped(project) -> None:
    root = project({SITE + "x-1.0.dist-info/RECORD": "x.py,,\n", SITE + "y-1.0.dist-info/METADATA": "Name: y\n"})
    index, _ = load(root)
    assert index.installed == {}


def test_windows_layout(project) -> None:
    root = project(
        {
            ".venv/Lib/site-packages/w-1.0.dist-info/METADATA": "Name: w\n",
            ".venv/Lib/site-packages/w-1.0.dist-info/RECORD": "w\\__init__.py,,\n",
        }
    )
    index, _ = load(root)
    assert index.package_for("w") == "w"


def test_a_venv_without_site_packages_is_a_warning(project) -> None:
    root = project({".venv/pyvenv.cfg": ""})
    _, warnings = load(root)
    assert warnings == [".venv: a virtualenv without a site-packages folder; its packages are not read"]


def test_declared_dependencies_match_by_name(project) -> None:
    root = project(
        {
            "requirements.txt": "# comment\nrequests>=2\n-r other.txt\n--index-url x\n"
            "Django==5.0 ; python_version>'3'\n",
            "requirements-dev.txt": "pytest\n",
            "requirements/nested.txt": "ignored\n",
        }
    )
    pyproject = {
        "project": {
            "dependencies": ["typing_extensions>=4", "attrs[tests]"],
            "optional-dependencies": {"web": ["Flask"]},
        },
        "dependency-groups": {"dev": ["ruff", {"include-group": "web"}]},
        "tool": {
            "poetry": {
                "dependencies": {"python": "^3.11", "Pendulum": "*"},
                "dev-dependencies": {"black": "*"},
                "group": {"docs": {"dependencies": {"Sphinx": "*"}}},
            }
        },
    }
    index, _ = load(root, venvs=[], pyproject=pyproject)
    assert index.declared == {
        "requests", "django", "pytest", "typing-extensions", "attrs", "flask", "ruff", "pendulum", "black", "sphinx",
    }  # fmt: skip
    assert index.package_for("typing_extensions") == "typing-extensions"
    assert index.package_for("django.db.models") == "django"
    assert index.package_for("yaml") is None
    assert index.package_for("python") is None


def test_installed_wins_over_declared(project) -> None:
    root = project({**dist("pyyaml", ["yaml/__init__.py"]), "requirements.txt": "yaml\n"})
    index, _ = load(root)
    assert index.package_for("yaml") == "pyyaml"


def test_declared_names_match_dotted_prefixes(project) -> None:
    root = project({"requirements.txt": "jaraco.abode\ngoogle-genai\nazure_eventhub\ngoogle\n"})
    index, _ = load(root, venvs=[], pyproject={})
    assert index.package_for("jaraco.abode.devices.light") == "jaraco-abode"
    assert index.package_for("google.genai.types") == "google-genai"
    assert index.package_for("azure.eventhub.aio") == "azure-eventhub"
    # The longest declared prefix wins; a prefix nobody declared names nothing.
    assert index.package_for("google.cloud.pubsub_v1") == "google"
    assert index.package_for("jaraco.functools") is None
