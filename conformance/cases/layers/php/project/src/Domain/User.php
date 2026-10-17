<?php
// SPDX-License-Identifier: MIT

namespace App\Domain;

use App\Infra\Clock;

final class User
{
    public function __construct(private Clock $clock)
    {
    }
}
