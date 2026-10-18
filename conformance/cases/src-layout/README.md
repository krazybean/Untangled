# src-layout

Where import roots come from (the scan passes `--source=tools`, see
`python/sources`):

- `src/` has no `__init__.py`, so it is an import root: `src/billing/invoice.py`
  is the module `billing.invoice`, and `manage.py` imports it as such.
- `pyproject.toml` lists `lib` in `[tool.setuptools.packages.find] where`, so
  `lib/vendored/helper.py` is `vendored.helper`.
- `tools/` is a root through `--source`, so `import devtool` finds
  `tools/devtool.py` from `manage.py` and from `scripts/run.py`.
- The project root is a root too: `scripts/run.py` is `scripts.run`, and each
  file's `module` comes from the deepest root that holds it.
