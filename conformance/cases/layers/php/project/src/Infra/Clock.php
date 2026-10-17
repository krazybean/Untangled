<?php
// SPDX-License-Identifier: MIT

namespace App\Infra;

final class Clock
{
    public function now(): \DateTimeImmutable
    {
        return new \DateTimeImmutable();
    }
}
