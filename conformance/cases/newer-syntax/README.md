# newer-syntax

`app/models.py` uses syntax from Python 3.12 to 3.14 (`type` statements, type
parameters, nested quotes in f-strings, `except` without parentheses). The
expected pairs are the same whichever Python runs the scanner: a Python that
cannot parse the file as a whole reads it statement by statement, and the
contexts (`type-checking`, `local`, `conditional`) still come from the blocks
the imports are in. The scan then warns that the file was read that way.
