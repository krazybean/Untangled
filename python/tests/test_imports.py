# SPDX-License-Identifier: GPL-2.0-only
import textwrap

from untangled.scanner.imports import (
    CONDITIONAL,
    DYNAMIC,
    FROM,
    IMPORT,
    LOCAL,
    TYPE_CHECKING,
    Import,
    collect,
    read_source,
)


def imports(code: str) -> list[Import]:
    result = collect(textwrap.dedent(code).encode())
    assert result.error is None
    return result.imports


def test_import_statements() -> None:
    assert imports("import a, b.c as d\n") == [Import(IMPORT, "a"), Import(IMPORT, "b.c")]


def test_from_imports_keep_their_names_and_level() -> None:
    assert imports("from a.b import c, d as e\nfrom .. import x\nfrom .m import *\n") == [
        Import(FROM, "a.b", 0, ("c", "d")),
        Import(FROM, None, 2, ("x",)),
        Import(FROM, "m", 1, ("*",)),
    ]


def test_imports_inside_functions_are_local_but_not_in_decorators_or_defaults() -> None:
    found = imports(
        """
        @decorate(__import__("deco"))
        def f(x=__import__("default")):
            import inner
            def g():
                from deep import x
        lam = lambda: __import__("lam")
        class C:
            import in_class
        """
    )
    contexts = {item.module: item.contexts for item in found}
    assert contexts == {
        "deco": frozenset(),
        "default": frozenset(),
        "inner": {LOCAL},
        "deep": {LOCAL},
        "lam": {LOCAL},
        "in_class": frozenset(),
    }


def test_async_functions_are_local_too() -> None:
    assert imports("async def f():\n    import a\n")[0].contexts == {LOCAL}


def test_type_checking_blocks() -> None:
    found = imports(
        """
        if TYPE_CHECKING:
            import a
        else:
            import b
        if typing.TYPE_CHECKING:
            import c
        if other:
            import d
        """
    )
    assert [(item.module, item.contexts) for item in found] == [
        ("a", {TYPE_CHECKING}),
        ("b", frozenset()),
        ("c", {TYPE_CHECKING}),
        ("d", frozenset()),
    ]


def test_try_with_an_import_error_handler_is_conditional() -> None:
    found = imports(
        """
        try:
            import fast
        except (ImportError, ValueError):
            import slow
        except KeyError:
            import other
        else:
            import after
        finally:
            import cleanup
        try:
            import plain
        except KeyError:
            pass
        try:
            import anything
        except:
            pass
        try:
            import broad
        except builtins.Exception:
            pass
        """
    )
    assert {item.module: item.contexts for item in found} == {
        "fast": {CONDITIONAL},
        "slow": {CONDITIONAL},
        "other": frozenset(),
        "after": frozenset(),
        "cleanup": frozenset(),
        "plain": frozenset(),
        "anything": {CONDITIONAL},
        "broad": {CONDITIONAL},
    }


def test_contexts_combine() -> None:
    found = imports(
        """
        def f():
            if TYPE_CHECKING:
                try:
                    import a
                except ModuleNotFoundError:
                    pass
        """
    )
    assert found[0].contexts == {LOCAL, TYPE_CHECKING, CONDITIONAL}


def test_dynamic_imports_with_literals() -> None:
    found = imports(
        """
        import importlib
        from importlib import import_module as load
        importlib.import_module("a.b")
        load("c")
        __import__("d.e")
        importlib.import_module(".x", "pkg.sub")
        importlib.import_module("..y", package="pkg.sub")
        load(".", "pkg")
        """
    )
    assert [item.module for item in found if item.kind == DYNAMIC] == ["a.b", "c", "d.e", "pkg.sub.x", "pkg.y", "pkg"]


def test_dynamic_imports_without_a_literal_keep_their_source_text() -> None:
    found = imports(
        """
        import importlib
        importlib.import_module(base  +
            name)
        __import__(f"p.{name}")
        importlib.import_module(".x")
        importlib.import_module("...x", "pkg")
        __import__(".x", "pkg")
        """
    )
    assert [item.text for item in found if item.kind == DYNAMIC] == [
        "base + name",
        'f"p.{name}"',
        '".x"',
        '"...x"',
        '".x"',
    ]
    assert all(item.module is None for item in found if item.kind == DYNAMIC)


def test_a_bare_import_module_counts_only_when_imported_from_importlib() -> None:
    assert [item.kind for item in imports('import_module("a")\n')] == []
    assert [item.module for item in imports('from importlib import import_module\nimport_module("a")\n')] == [
        "importlib",
        "a",
    ]


def test_calls_without_arguments_are_skipped() -> None:
    assert imports("__import__()\nimportlib.import_module(*names)\n") == []


def test_python_2_code_is_an_error_with_no_imports() -> None:
    result = collect(b'import os\nprint "hello"\n')
    assert result.imports == []
    assert result.error is not None and result.error.startswith("cannot parse as Python 3: ")
    assert "(line 2)" in result.error


def test_null_bytes_are_an_error() -> None:
    assert collect(b"import a\x00\n").error is not None


def test_deeply_nested_code_does_not_hit_the_recursion_limit() -> None:
    # A long chain of + is a binary operation nested 2000 deep, past the recursion limit.
    code = "x = " + " + ".join(["1"] * 2000) + ' + __import__("deep")\n'
    assert [item.module for item in imports(code)] == ["deep"]


def test_source_is_decoded_with_its_coding_comment() -> None:
    assert read_source("# -*- coding: latin-1 -*-\nx = 'café'\n".encode("latin-1")).endswith("'café'\n")


def test_source_with_a_bom_is_decoded() -> None:
    assert read_source(b"\xef\xbb\xbfimport a\n") == "import a\n"


def test_source_that_is_not_utf8_is_read_as_windows_1252() -> None:
    assert read_source("from café import x # €\n".encode("cp1252")) == "from café import x # €\n"
    assert collect("from café import x\n".encode("cp1252")).imports == [Import(FROM, "café", 0, ("x",))]


def test_source_with_a_wrong_coding_comment_is_read_as_windows_1252() -> None:
    assert read_source(b"# coding: nonsense\nx = 1\n") == "# coding: nonsense\nx = 1\n"
