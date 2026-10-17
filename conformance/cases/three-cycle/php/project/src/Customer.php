<?php
// SPDX-License-Identifier: MIT

namespace Shop;

final class Customer
{
    public static function current(): self
    {
        return new self();
    }

    public function cart(): Cart
    {
        return new Cart();
    }
}
