<?php
// SPDX-License-Identifier: MIT

namespace App\Http;

final class Router
{
    public function dispatch(): void
    {
        (new UserController($this))->show(1);
    }
}
