# import-kinds

Every kind of reference `app/main.py` can make, and the contexts it can make
them in:

- `if TYPE_CHECKING:` and `if typing.TYPE_CHECKING:` give `type-checking`.
- `try: import ujson as json` / `except ImportError: import json` gives
  `conditional` to both; `ujson` is not installed, so it is unresolved.
- Imports in a method body are `local`; the import in the class body is not.
- `importlib.import_module("app.plugins.pdf")`, `load(".plugins.sheet",
  "app")` (`import_module` imported as `load`, with a relative name and a
  literal package) and `__import__("app.models")` are `dynamic` and resolve.
- `load(name)` and an f-string are `unresolved:dynamic:<source text>`.
- An edge's kinds are the union over its references: `app/models.py` is
  reached by a `type-checking` `from`, a `local` `import` and a `dynamic`
  call, three references.
