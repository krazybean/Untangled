<?php
// SPDX-License-Identifier: MIT

namespace App\Http;

use App\Domain\Order;
use App\Infra\UserRepository;

final class UserController
{
    public function __construct(private Router $router)
    {
    }

    public function show(int $id, ?UserRepository $users = null): ?Order
    {
        return null;
    }
}
