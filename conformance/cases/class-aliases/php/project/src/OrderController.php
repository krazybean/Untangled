<?php
// SPDX-License-Identifier: MIT

namespace App;

use DB;
use Redirect;

final class OrderController
{
    public function store(): mixed
    {
        DB::transaction(fn () => \Cart::store());
        \Log::info('stored');
        $total = \Money::sum();
        \Telescope::tag(fn () => ['orders']);
        return Redirect::back();
    }
}
