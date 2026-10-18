# relative-imports

Relative imports resolve from the importing file's package:

- In `pkg/__init__.py`, `from . import a` is `pkg/a.py` (the package of an
  `__init__.py` is the package itself).
- In `pkg/sub/c.py`, `from .. import b` is `pkg/b.py` and `from ..a import
  thing` is `pkg/a.py`; `from ...outside import name` goes above the top-level
  package and is `unresolved:module:...outside`, written as in the code.
- `from .missing import other` in `pkg/b.py` is `unresolved:module:pkg.missing`.
- `manage.py` is a top-level module, in no package, so `from .settings import
  DEBUG` is `unresolved:module:.settings`.
- Every edge carries the `relative` kind.
