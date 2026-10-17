<?php
// SPDX-License-Identifier: MIT

namespace App\Domain;

final class Order
{
    public function __construct(public readonly User $customer)
    {
    }
}
