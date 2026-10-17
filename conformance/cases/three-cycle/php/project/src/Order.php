<?php
// SPDX-License-Identifier: MIT

namespace Shop;

final class Order
{
    public function __construct(private Cart $cart)
    {
    }

    public function customer(): Customer
    {
        return Customer::current();
    }
}
