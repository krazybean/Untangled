# stdlib-and-packages

Builtins and third-party packages. The project has a virtualenv in `.venv/`
(only the `.dist-info` folders the scanner reads, with their `METADATA` and
`RECORD`) and a `requirements.txt`:

- Standard library modules are `builtin:<top-level>`: `os.path` is
  `builtin:os`. `distutils`, removed in Python 3.12, is still a builtin, on
  every Python. `from __future__ import annotations` is `builtin:__future__`.
- `import yaml` and `import _yaml` are `pypi:pyyaml`, read from the `RECORD`
  of `PyYAML` (an import name that differs from the distribution name), and
  `import _cffi_backend` is `pypi:cffi`, from a native module in its `RECORD`.
- `google/` is installed by `google-auth` and `protobuf`: `google.auth.jwt`
  is `pypi:google-auth` and `google.protobuf` is `pypi:protobuf`, by the
  longest installed prefix, while `import google` alone names neither and is
  unresolved.
- `typing_extensions` and `django` are declared in `requirements.txt` but not
  installed: they match by name, `pypi:typing-extensions` and `pypi:django`.
- `requests` is neither installed nor declared: unresolved.
- `logging.py` at the project root shadows the standard library's `logging`,
  so `import logging` points at it, as when Python runs `app.py`.
