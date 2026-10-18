# extension-modules

Modules without a `.py` file. A stub (`.pyi`), a Cython source (`.pyx`) or a
compiled extension (`.so`, `.pyd`) in the project is a project module, so an
import of it is an edge to that file, an internal node with its module name.
These files are never scanned (they record no edges of their own).

- `fast._speedups` has both `_speedups.pyi` and `_speedups.pyx`: the stub wins.
- `fast._native` is only `_native.cpython-312-x86_64-linux-gnu.so`, whose module
  name is the part before the first dot.
- `fast.helpers` has `helpers.py` and `helpers.pyi`: the `.py` file wins, and is
  scanned as usual.
- `fast._ctypes_only` is only a stub, as for an extension built from C.
- `fast._not_built` has no file at all and is `unresolved:module:fast._not_built`.
