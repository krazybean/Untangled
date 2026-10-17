<?php
// SPDX-License-Identifier: MIT

namespace App;

use Composer\InstalledVersions;

require_once __DIR__ . '/../vendor/autoload.php';
require_once 'Legacy/helpers.php';

final class Invoice implements \Stringable
{
    public function __toString(): string
    {
        $order = new \Legacy_Order();
        return legacy_total($order) . ' ' . InstalledVersions::getRootPackage()['name'];
    }
}
