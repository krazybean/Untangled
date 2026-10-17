<?php
// SPDX-License-Identifier: MIT

const APP_VERSION = '1.0';

function format_total(int $cents): string
{
    return number_format($cents / 100, 2);
}

require_once __DIR__ . '/../legacy/bootstrap.php';
