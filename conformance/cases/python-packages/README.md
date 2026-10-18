# python-packages

How Python packages map onto files:

- `from shop import pricing` imports the submodule `shop/pricing.py`, while
  `from shop import VERSION` imports a name defined in `shop/__init__.py`, so
  that edge points at `__init__.py`. With `shop/__init__.py` re-exporting
  `Cart`, the two files depend on each other, as they do when Python runs them.
- `shop/catalog/` has no `__init__.py`: a namespace package. `import
  shop.catalog.items` points at `items.py`; `import shop.catalog` points at no
  file and adds no edge; `from shop.catalog import missing` is unresolved,
  since a namespace package has only submodules.
- `from shop.missing import thing` is `unresolved:module:shop.missing`, never
  an edge to `shop/__init__.py`.
- `util.py` and `util/__init__.py` both exist; `import util` points at the
  package, as in Python. `util.py` is still scanned.
- `scripts/my-tool.py` has no module name (`my-tool` is not an identifier),
  so its node has no `module`.
- `from shop import *` points at `shop/__init__.py`.
