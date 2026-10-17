<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Scanner;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Untangled\Composer\Package;
use Untangled\Scanner\FileScanner;
use Untangled\Scanner\VendorIndex;

final class VendorIndexTest extends TestCase
{
    /** @return iterable<string, array{string, ?string}> */
    public static function classes(): iterable
    {
        yield 'psr-4 prefix' => ['Monolog\\Logger', 'monolog/monolog'];
        yield 'psr-4 is case-insensitive' => ['monolog\\handler\\StreamHandler', 'monolog/monolog'];
        yield 'psr-4 needs the separator' => ['MonologExtra\\X', null];
        yield 'psr-0 underscore prefix' => ['Twig_Environment', 'twig/twig'];
        yield 'psr-0 bare prefix, namespaced' => ['Swift\\Mailer', 'swiftmailer/swiftmailer'];
        yield 'psr-0 bare prefix, underscored' => ['Swift_Mailer', 'swiftmailer/swiftmailer'];
        yield 'psr-0 bare prefix, exact' => ['Swift', 'swiftmailer/swiftmailer'];
        yield 'psr-0 bare prefix is not a string prefix' => ['Swiftly\\X', null];
        yield 'longest prefix wins' => ['Acme\\Core\\Kernel', 'acme/core'];
        yield 'shorter prefix still matches the rest' => ['Acme\\Util\\Str', 'acme/all'];
        yield 'leading backslash on the prefix is ignored' => ['Lead\\X', 'lead/pkg'];
        yield 'unknown' => ['Nobody\\Knows', null];
    }

    #[DataProvider('classes')]
    public function testPackageFor(string $class, ?string $package): void
    {
        $index = new VendorIndex([
            new Package('acme/all', ['psr-4' => ['Acme\\' => 'src/']], null),
            new Package('acme/core', ['psr-4' => ['Acme\\Core\\' => 'src/']], null),
            new Package('greedy/pkg', ['psr-4' => ['' => 'src/']], null),
            new Package('lead/pkg', ['psr-4' => ['\\Lead\\' => 'src/']], null),
            new Package('monolog/monolog', ['psr-4' => ['Monolog\\' => 'src/Monolog']], null),
            new Package('swiftmailer/swiftmailer', ['psr-0' => ['Swift' => 'lib/']], null),
            new Package('twig/twig', ['psr-0' => ['Twig_' => 'lib/']], null),
        ], new FileScanner());
        self::assertSame($package, $index->packageFor($class));
    }

    public function testTheFirstPackageWithAPrefixKeepsIt(): void
    {
        $index = new VendorIndex([
            new Package('a/one', ['psr-4' => ['Same\\' => 'src/']], null),
            new Package('b/two', ['psr-4' => ['Same\\' => 'src/']], null),
        ], new FileScanner());
        self::assertSame('a/one', $index->packageFor('Same\\X'));
    }

    public function testClassmapPackagesNeedAnInstallPath(): void
    {
        $index = new VendorIndex([new Package('acme/legacy', ['classmap' => ['lib/']], null)], new FileScanner());
        self::assertNull($index->packageFor('LegacyThing'));
    }
}
