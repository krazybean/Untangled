<?php
// SPDX-License-Identifier: MIT

namespace Shop;

final class Cart
{
    public function checkout(): Order
    {
        return new Order($this);
    }
}
