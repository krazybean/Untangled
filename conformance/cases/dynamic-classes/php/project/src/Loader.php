<?php
// SPDX-License-Identifier: MIT

namespace App;

final class Loader
{
    private const LABEL = 'loader';

    public function create(string $class): Plugin
    {
        return new $class();
    }

    public function build(callable $factory): object
    {
        return new ($factory())(1);
    }

    public function describe(string $class, object $subject): bool
    {
        $class::boot();
        $version = $class::VERSION;
        $own = $this::class . $this::LABEL;
        return $subject instanceof $class && $subject::class !== Plugin::class;
    }
}
