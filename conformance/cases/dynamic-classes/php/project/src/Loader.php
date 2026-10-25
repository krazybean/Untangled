<?php

namespace App;

final class Loader
{
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
        return $subject instanceof $class && $subject::class !== Plugin::class;
    }
}
