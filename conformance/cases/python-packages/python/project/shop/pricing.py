# SPDX-License-Identifier: MIT

# shop/catalog/ has no __init__.py: a namespace package.
import shop.catalog.items


def total(cart) -> float:
    return sum(item.price for item in shop.catalog.items.ITEMS)
