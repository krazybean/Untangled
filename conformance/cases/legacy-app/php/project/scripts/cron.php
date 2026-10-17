<?php
// SPDX-License-Identifier: MIT

// Not autoloaded and not passed with --source: not scanned, and the scan warns about it.
(new App\Invoice())->__toString();
