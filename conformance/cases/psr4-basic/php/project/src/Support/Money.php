<?php
// SPDX-License-Identifier: MIT

namespace App\Support;

final class Money
{
    public function add(self $other): static
    {
        return $this;
    }
}
