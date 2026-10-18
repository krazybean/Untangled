# SPDX-License-Identifier: MIT

# Re-exports Cart, so `from shop import Cart` works.
from shop.cart import Cart

VERSION = "1.0"
__all__ = ["Cart", "VERSION"]
