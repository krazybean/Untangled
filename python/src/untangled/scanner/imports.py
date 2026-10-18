# SPDX-License-Identifier: GPL-2.0-only
"""Reads one Python file's imports with the ast module (spec/languages/python.md)."""

import ast
import io
import re
import tokenize
from dataclasses import dataclass, field

from untangled.text import utf8

IMPORT = "import"
FROM = "from"
DYNAMIC = "dynamic"

LOCAL = "local"
TYPE_CHECKING = "type-checking"
CONDITIONAL = "conditional"

_IMPORT_ERRORS = {"ImportError", "ModuleNotFoundError"}


@dataclass(frozen=True)
class Import:
    """One import statement, or one dynamic import call.

    `module` is the dotted name as written, without leading dots (None for
    `from . import x`), and `level` the number of leading dots. `names` holds the
    names of a `from` import. A dynamic import whose argument is not a string literal
    has no module and keeps its source text in `text`.
    """

    kind: str
    module: str | None
    level: int = 0
    names: tuple[str, ...] = ()
    contexts: frozenset[str] = frozenset()
    text: str | None = None


@dataclass
class FileImports:
    imports: list[Import] = field(default_factory=list)
    error: str | None = None


def read_source(raw: bytes) -> str:
    """Decodes a file as Python does (a BOM or a PEP 263 coding comment, else UTF-8);
    a file that is not valid in that encoding is read as Windows-1252."""
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        return raw.decode(encoding)
    except (SyntaxError, LookupError, UnicodeDecodeError):
        return utf8(raw)


def collect(raw: bytes) -> FileImports:
    source = read_source(raw)
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        where = f" (line {error.lineno})" if error.lineno else ""
        return FileImports(error=f"cannot parse as Python 3: {error.msg}{where}")
    except (ValueError, RecursionError, MemoryError) as error:
        return FileImports(error=f"cannot parse as Python 3: {error}")
    return FileImports(imports=_Collector(source).run(tree))


class _Collector:
    def __init__(self, source: str) -> None:
        self.source = source
        self.imports: list[Import] = []
        # Names that call importlib.import_module: `importlib.import_module` always,
        # a bare name only once the file imports it from importlib.
        self.import_module_names: set[str] = set()

    def run(self, tree: ast.Module) -> list[Import]:
        # An explicit stack instead of recursion: generated code can nest deeper than
        # Python's recursion limit.
        stack: list[tuple[ast.AST, frozenset[str]]] = [(tree, frozenset())]
        while stack:
            node, contexts = stack.pop()
            children = self.visit(node, contexts)
            stack.extend(reversed(children))
        return self.imports

    def visit(self, node: ast.AST, contexts: frozenset[str]) -> list[tuple[ast.AST, frozenset[str]]]:
        if isinstance(node, ast.Import):
            for alias in node.names:
                self.imports.append(Import(IMPORT, alias.name, contexts=contexts))
            return []
        if isinstance(node, ast.ImportFrom):
            names = tuple(alias.name for alias in node.names)
            self.imports.append(Import(FROM, node.module, node.level, names, contexts))
            if node.module == "importlib" and node.level == 0:
                for alias in node.names:
                    if alias.name == "import_module":
                        self.import_module_names.add(alias.asname or alias.name)
            return []
        if isinstance(node, ast.Call):
            self.call(node, contexts)
        elif isinstance(node, ast.If) and _is_type_checking(node.test):
            return (
                [(node.test, contexts)]
                + [(child, contexts | {TYPE_CHECKING}) for child in node.body]
                + [(child, contexts) for child in node.orelse]
            )
        elif isinstance(node, (ast.Try, ast.TryStar)) and any(_catches_import_error(h) for h in node.handlers):
            guarded = contexts | {CONDITIONAL}
            return (
                [(child, guarded) for child in node.body]
                + [(handler, guarded if _catches_import_error(handler) else contexts) for handler in node.handlers]
                + [(child, contexts) for child in node.orelse + node.finalbody]
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            # Decorators, defaults and annotations run when the function is defined;
            # only the body runs when it is called.
            body = node.body if isinstance(node.body, list) else [node.body]
            outer = [child for child in ast.iter_child_nodes(node) if child not in body]
            return [(child, contexts) for child in outer] + [(child, contexts | {LOCAL}) for child in body]
        return [(child, contexts) for child in ast.iter_child_nodes(node)]

    def call(self, node: ast.Call, contexts: frozenset[str]) -> None:
        func = node.func
        is_dynamic = (
            isinstance(func, ast.Name) and (func.id == "__import__" or func.id in self.import_module_names)
        ) or (
            isinstance(func, ast.Attribute)
            and func.attr == "import_module"
            and isinstance(func.value, ast.Name)
            and func.value.id == "importlib"
        )
        if not is_dynamic or not node.args or isinstance(node.args[0], ast.Starred):
            return
        argument = node.args[0]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            name = argument.value
            level = len(name) - len(name.lstrip("."))
            if not level and name:
                self.imports.append(Import(DYNAMIC, name, contexts=contexts))
                return
            # import_module(".x", "pkg") imports pkg.x; without a literal package it is
            # an error at run time, and __import__ has no such form.
            package = _string_argument(node, 1, "package")
            base = package.split(".") if package else []
            if _is_import_module(func) and base and level - 1 < len(base):
                rest = name[level:]
                module = ".".join(base[: len(base) - (level - 1)]) + ("." + rest if rest else "")
                self.imports.append(Import(DYNAMIC, module, contexts=contexts))
                return
        text = ast.get_source_segment(self.source, argument) or ast.unparse(argument)
        self.imports.append(Import(DYNAMIC, None, contexts=contexts, text=re.sub(r"\s+", " ", text).strip()))


def _is_import_module(func: ast.expr) -> bool:
    return not (isinstance(func, ast.Name) and func.id == "__import__")


def _string_argument(node: ast.Call, position: int, keyword: str) -> str | None:
    value: ast.expr | None = node.args[position] if len(node.args) > position else None
    for item in node.keywords:
        if item.arg == keyword:
            value = item.value
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _catches_import_error(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    for item in types:
        name = item.id if isinstance(item, ast.Name) else item.attr if isinstance(item, ast.Attribute) else None
        if name in _IMPORT_ERRORS or name in ("Exception", "BaseException"):
            return True
    return False
