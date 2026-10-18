# legacy-python

Older code and test folders:

- `legacy/old.py` is Python 2 (`print "hello"`): it does not parse, so it is a
  node with no edges, and the scan warns.
- `legacy/cookie.py` is saved as Latin-1 and says so in a coding comment;
  `legacy/menu.py` is saved as Windows-1252 without one, which Python would
  refuse, and is read as Windows-1252. Both import `legacy.café` (written in
  their own encoding), which resolves to `legacy/café.py`, and the document
  carries the name as UTF-8.
- `tests/` and `legacy/conftest.py` are test files and are not scanned
  without `--dev`.
- `legacy/test/` is a test folder too, but `legacy/helpers.py` imports
  `legacy/test/client.py`, so that file is scanned (as Django's
  `django/test/` is real code). `legacy/test/__init__.py` is not imported and
  not scanned.
