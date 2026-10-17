<?php
// SPDX-License-Identifier: MIT

namespace App\Billing;

use App\Support\Money;
use App\Support\Clock;

final class Invoice extends Document implements Payable
{
    public function __construct(private Money $total, private ?Clock $clock = null)
    {
    }

    public function issue(): \DateTimeImmutable
    {
        $tax = new Tax();
        return new \DateTimeImmutable('@' . Tax::RATE);
    }

    public function legacy(): void
    {
        \App\Legacy\Ledger::post($this);
    }
}
