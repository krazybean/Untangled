<?php
// SPDX-License-Identifier: MIT

namespace App;

require_once __DIR__ . '/../vendor/acme/util/src/functions.php';

final class Export
{
    public function pdf(): \FPDF_Document
    {
        return new \FPDF_Document();
    }

    public function name(\Acme\Util\Str $str): string
    {
        return acme_slug('report');
    }
}
