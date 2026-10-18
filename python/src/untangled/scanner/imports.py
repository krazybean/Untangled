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
    """Why the file has no imports: it could not be read or parsed at all."""
    partial: str | None = None
    """Why the file was read statement by statement (see read_statements): its parse error."""


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
        message = f"cannot parse as Python 3: {error.msg}{where}"
        found = read_statements(source) if "\0" not in source else None
        return FileImports(error=message) if found is None else FileImports(imports=found, partial=message)
    except (ValueError, RecursionError, MemoryError) as error:
        return FileImports(error=f"cannot parse as Python 3: {error}")
    return FileImports(imports=_Collector(source).run(tree))


class _Collector:
    def __init__(self, source: str, import_module_names: set[str] | None = None) -> None:
        self.source = source
        self.imports: list[Import] = []
        # Names that call importlib.import_module: `importlib.import_module` always,
        # a bare name only once the file imports it from importlib.
        self.import_module_names: set[str] = set() if import_module_names is None else import_module_names

    def run(self, tree: ast.AST, contexts: frozenset[str] = frozenset()) -> list[Import]:
        # An explicit stack instead of recursion: generated code can nest deeper than
        # Python's recursion limit.
        stack: list[tuple[ast.AST, frozenset[str]]] = [(tree, contexts)]
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


# Reading a file statement by statement, for code that the running Python cannot parse
# as a whole, usually because it uses newer syntax (`except A, B:` from Python 3.14 on
# Python 3.13, `type X = ...` from 3.12 on 3.11). The tokenizer is far more stable across
# versions than the parser: the file is split into logical lines, nested by indentation,
# and each simple statement is parsed on its own. Block headers are never parsed; only
# their keywords and indentation give a statement its contexts.

_COMPOUND = {"if", "elif", "else", "for", "while", "try", "except", "finally", "with", "def", "class", "async"}
_SOFT_COMPOUND = {"match", "case"}
_OPENING = {"(", "[", "{"}
_CLOSING = {")", "]", "}"}
_PYTHON2_NUMBER = re.compile(r"0[0-7]+|[0-9]+[lL]")


@dataclass
class _Line:
    tokens: list[tokenize.TokenInfo]
    children: list["_Line"] = field(default_factory=list)

    @property
    def keyword(self) -> str:
        first = self.tokens[0]
        if first.string == "async" and len(self.tokens) > 1:
            return self.tokens[1].string
        return first.string if first.type == tokenize.NAME else ""


def read_statements(source: str) -> list[Import] | None:
    """The imports of a file read statement by statement, or None when the file cannot be
    tokenized or looks like Python 2 (whose imports do not mean what they mean in Python 3)."""
    try:
        lines = _lines(source)
    except (tokenize.TokenError, SyntaxError):
        return None
    reader = _StatementReader(source)
    return reader.imports if reader.read(lines, frozenset()) else None


def _lines(source: str) -> list[_Line]:
    """The file's logical lines, each with the lines of the block it opens as children."""
    top: list[_Line] = []
    stack: list[tuple[int, list[_Line]]] = [(-1, top)]
    depth = 0
    tokens: list[tokenize.TokenInfo] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.INDENT:
            depth += 1
        elif token.type == tokenize.DEDENT:
            depth -= 1
        elif token.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
            if tokens:
                while stack[-1][0] >= depth:
                    stack.pop()
                line = _Line(tokens)
                stack[-1][1].append(line)
                stack.append((depth, line.children))
                tokens = []
        elif token.type not in (tokenize.NL, tokenize.COMMENT):
            tokens.append(token)
    return top


def _split(tokens: list[tokenize.TokenInfo], separator: str) -> list[list[tokenize.TokenInfo]]:
    """Splits tokens on an operator outside brackets."""
    parts: list[list[tokenize.TokenInfo]] = [[]]
    depth = 0
    for token in tokens:
        if token.type == tokenize.OP and token.string in _OPENING:
            depth += 1
        elif token.type == tokenize.OP and token.string in _CLOSING:
            depth -= 1
        if depth == 0 and token.type == tokenize.OP and token.string == separator:
            parts.append([])
        else:
            parts[-1].append(token)
    return [part for part in parts if part]


def _header_end(line: _Line) -> int | None:
    """The index of the colon that ends a block header, or None for a simple statement."""
    keyword = line.keyword
    if keyword in _SOFT_COMPOUND:
        last = line.tokens[-1]
        return len(line.tokens) - 1 if last.type == tokenize.OP and last.string == ":" else None
    if keyword not in _COMPOUND or (keyword == "async" and len(line.tokens) < 2):
        return None
    depth = 0
    lambdas = 0
    for index, token in enumerate(line.tokens):
        if token.type == tokenize.OP and token.string in _OPENING:
            depth += 1
        elif token.type == tokenize.OP and token.string in _CLOSING:
            depth -= 1
        elif depth == 0 and token.type == tokenize.NAME and token.string == "lambda":
            lambdas += 1
        elif depth == 0 and token.type == tokenize.OP and token.string == ":":
            if not lambdas:
                return index
            lambdas -= 1
    return None


def _catches_import_errors(header: list[tokenize.TokenInfo]) -> bool:
    """Whether an `except` header (without its colon) catches import errors, as _catches_import_error."""
    names = [token.string for token in header[1:] if token.type == tokenize.NAME]
    if "as" in names:
        names = names[: names.index("as")]
    caught = [token for token in header[1:] if not (token.type == tokenize.OP and token.string == "*")]
    return not caught or any(name in _IMPORT_ERRORS or name in ("Exception", "BaseException") for name in names)


def _looks_like_python2(tokens: list[tokenize.TokenInfo]) -> bool:
    """Whether a statement that does not parse uses Python 2 only syntax."""
    first = tokens[0]
    second = tokens[1] if len(tokens) > 1 else None
    if first.string in ("print", "exec") and second is not None:
        if second.type != tokenize.OP or second.string == ">>":
            return True
    if first.string == "raise" and len(_split(tokens, ",")) > 1:
        return True
    return _has_python2_tokens(tokens)


def _has_python2_tokens(tokens: list[tokenize.TokenInfo]) -> bool:
    """Whether tokens hold something that is never Python 3: `<>`, backticks, 0777, 10L."""
    for token, after in zip(tokens, [*tokens[1:], None], strict=True):
        if token.type not in (tokenize.OP, tokenize.ERRORTOKEN, tokenize.NUMBER):
            continue  # such as the text of an f-string, which tokenizers since Python 3.12 split up
        if token.string in ("<>", "`") or (
            token.string == "<" and after is not None and after.string == ">" and after.start == token.end
        ):
            return True
        if token.type == tokenize.NUMBER:
            # Older tokenizers split 0777 into 0 and 777, and 10L into 10 and L.
            text = token.string + (after.string if after is not None and after.start == token.end else "")
            if _PYTHON2_NUMBER.fullmatch(text):
                return True
    return False


class _StatementReader:
    def __init__(self, source: str) -> None:
        self.source_lines = source.splitlines(keepends=True)
        self.imports: list[Import] = []
        self.import_module_names: set[str] = set()

    def read(self, lines: list[_Line], contexts: frozenset[str]) -> bool:
        """Reads a block's lines; False when one looks like Python 2."""
        guarded = False
        for index, line in enumerate(lines):
            end = _header_end(line)
            if end is None:
                if not all(self.statement(part, contexts) for part in _split(line.tokens, ";")):
                    return False
                continue
            if _has_python2_tokens(line.tokens[:end]):
                return False
            keyword = line.keyword
            self.header(line.tokens[: end + 1], keyword, contexts)
            inner = contexts
            if keyword == "def":
                inner = contexts | {LOCAL}
            elif keyword in ("if", "elif") and _header_is_type_checking(line.tokens[1:end]):
                inner = contexts | {TYPE_CHECKING}
            elif keyword == "try":
                handlers = []
                for sibling in lines[index + 1 :]:
                    if sibling.keyword != "except":
                        break
                    handlers.append(sibling)
                guarded = any(
                    _catches_import_errors(handler.tokens[: _header_end(handler) or len(handler.tokens)])
                    for handler in handlers
                )
                inner = contexts | {CONDITIONAL} if guarded else contexts
            elif keyword == "except" and guarded and _catches_import_errors(line.tokens[:end]):
                inner = contexts | {CONDITIONAL}
            body = line.tokens[end + 1 :]
            if body and not all(self.statement(part, inner) for part in _split(body, ";")):
                return False
            if not self.read(line.children, inner):
                return False
        return True

    def header(self, tokens: list[tokenize.TokenInfo], keyword: str, contexts: frozenset[str]) -> None:
        """Reads the expressions of a block header, such as `if import_module("a"):` or a
        function's defaults, by parsing it with an empty body. A header that does not parse
        is skipped: it holds no import statement, only, rarely, a dynamic import."""
        if keyword in ("try", "else", "finally", "except", "match", "case"):
            return
        text = self.text(tokens)
        if keyword == "elif":
            text = text[len("el") :]
        self.parse(text + " pass", contexts)

    def statement(self, tokens: list[tokenize.TokenInfo], contexts: frozenset[str]) -> bool:
        text = self.text(tokens)
        if tokens[0].string == "@":
            text += "\ndef _(): pass"  # a decorator, whose function is on the next line
        return self.parse(text, contexts) or not _looks_like_python2(tokens)

    def parse(self, text: str, contexts: frozenset[str]) -> bool:
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            return False
        collector = _Collector(text, self.import_module_names)
        self.imports.extend(collector.run(tree, contexts))
        return True

    def text(self, tokens: list[tokenize.TokenInfo]) -> str:
        (start_row, start_col), (end_row, end_col) = tokens[0].start, tokens[-1].end
        if start_row == end_row:
            return self.source_lines[start_row - 1][start_col:end_col]
        rows = self.source_lines[start_row - 1 : end_row]
        return rows[0][start_col:] + "".join(rows[1:-1]) + rows[-1][:end_col]


def _header_is_type_checking(test: list[tokenize.TokenInfo]) -> bool:
    """`if TYPE_CHECKING:` or `if typing.TYPE_CHECKING:` (or any `x.TYPE_CHECKING`)."""
    names = [token.string for token in test]
    return names == ["TYPE_CHECKING"] or (
        len(names) >= 3 and names[-1] == "TYPE_CHECKING" and all(n == "." for n in names[1:-1:2])
    )
