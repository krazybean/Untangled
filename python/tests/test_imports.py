# SPDX-License-Identifier: GPL-2.0-only
import textwrap
from pathlib import Path

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
    read_statements,
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


# Statement by statement, for files the running Python cannot parse as a whole.


def test_a_file_that_does_not_parse_is_read_statement_by_statement() -> None:
    code = textwrap.dedent(
        """
        import a
        x = = 1  # not Python in any version
        from typing import TYPE_CHECKING
        if TYPE_CHECKING: import tc
        class K:
            def f(self):
                try:
                    import guarded; import also
                except (ImportError, ValueError):
                    import fallback
                except KeyError:
                    import plain
                y = importlib.import_module("dyn")
        """
    )
    result = collect(code.encode())
    assert result.error is None
    assert result.partial == "cannot parse as Python 3: invalid syntax (line 3)"
    assert result.imports == [
        Import(IMPORT, "a"),
        Import(FROM, "typing", 0, ("TYPE_CHECKING",)),
        Import(IMPORT, "tc", contexts=frozenset({TYPE_CHECKING})),
        Import(IMPORT, "guarded", contexts=frozenset({LOCAL, CONDITIONAL})),
        Import(IMPORT, "also", contexts=frozenset({LOCAL, CONDITIONAL})),
        Import(IMPORT, "fallback", contexts=frozenset({LOCAL, CONDITIONAL})),
        Import(IMPORT, "plain", contexts=frozenset({LOCAL})),
        Import(DYNAMIC, "dyn", contexts=frozenset({LOCAL})),
    ]


def test_statement_by_statement_reads_what_the_parser_reads() -> None:
    # Every file of this library parses whole: reading it statement by statement must
    # find the same imports, in the same order, with the same contexts.
    sources = sorted((Path(__file__).resolve().parents[1] / "src").rglob("*.py")) + sorted(
        Path(__file__).resolve().parent.glob("*.py")
    )
    assert len(sources) > 20
    for path in sources:
        source = path.read_text(encoding="utf-8")
        assert read_statements(source) == collect(path.read_bytes()).imports, path


def test_newer_syntax_is_read_statement_by_statement() -> None:
    code = textwrap.dedent(
        """
        type Alias = list[int]
        class Box[T]:
            def f(self) -> str:
                import inner
                return f"{self.x["k"]}"
        try:
            import fast
        except ImportError, ModuleNotFoundError:
            import slow
        match command:
            case "go":
                import go
        lam = lambda: (yield)
        @decorate(lambda x: x)
        async def g[T](x: T) -> T: from . import rel
        """
    )
    assert read_statements(code) == [
        Import(IMPORT, "inner", contexts=frozenset({LOCAL})),
        Import(IMPORT, "fast", contexts=frozenset({CONDITIONAL})),
        Import(IMPORT, "slow", contexts=frozenset({CONDITIONAL})),
        Import(IMPORT, "go"),
        Import(FROM, None, 1, ("rel",), frozenset({LOCAL})),
    ]


def test_python_2_files_are_not_read_statement_by_statement() -> None:
    for statement in ('print "hello"', 'exec "code"', "raise E, 'message'", "x = 0777",
                      "x = 10L", "x = `y`", "if a <> b: pass"):  # fmt: skip
        result = collect(f"import urllib2\n{statement}\n".encode())
        assert result.imports == [] and result.error is not None, statement


def test_a_file_that_cannot_be_tokenized_is_an_error() -> None:
    result = collect(b"import a\nx = (1,\n")
    assert result.imports == [] and result.error is not None


def test_statement_by_statement_reads_headers_and_decorators() -> None:
    code = textwrap.dedent(
        """
        x = = 1
        if import_module("in_if"):
            pass
        elif __import__("in_elif"):
            pass
        elif TYPE_CHECKING:
            import tc
        else:
            import plain
        @register(__import__("deco"))
        def f(arg=__import__("default")):
            import inner
        """
    )
    assert read_statements(code) == [
        Import(DYNAMIC, "in_elif"),
        Import(IMPORT, "tc", contexts=frozenset({TYPE_CHECKING})),
        Import(IMPORT, "plain"),
        Import(DYNAMIC, "deco"),
        Import(DYNAMIC, "default"),
        Import(IMPORT, "inner", contexts=frozenset({LOCAL})),
    ]
