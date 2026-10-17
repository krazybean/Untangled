<?php
// SPDX-License-Identifier: MIT

if (\PHP_VERSION_ID < 80000) {
    interface Stringable
    {
        public function __toString(): string;
    }
}
