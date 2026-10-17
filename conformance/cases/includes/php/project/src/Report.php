<?php
// SPDX-License-Identifier: MIT

final class Report
{
    public function render(string $theme): string
    {
        $config = require dirname(__DIR__) . '/config/app.php';
        include $theme . '/header.php';
        include 'config/missing.php';
        return format_total(100) . APP_VERSION . strlen($theme);
    }
}
