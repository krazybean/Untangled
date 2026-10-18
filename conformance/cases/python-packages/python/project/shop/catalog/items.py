# SPDX-License-Identifier: MIT

# Importing the namespace package itself points at no file, so it adds no edge.
import shop.catalog

# A namespace package has no attributes, only submodules, and there is no missing.py.
from shop.catalog import missing

ITEMS = []
