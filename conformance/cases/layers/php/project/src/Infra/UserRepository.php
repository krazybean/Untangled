<?php
// SPDX-License-Identifier: MIT

namespace App\Infra;

use App\Cache\Store;
use App\Domain\User;

final class UserRepository
{
    public function __construct(private Clock $clock, private Store $cache)
    {
    }

    public function find(int $id): User
    {
        return new User($this->clock);
    }
}
