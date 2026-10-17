<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Scanner;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Untangled\Composer\Package;
use Untangled\Scanner\ClassAliases;
use Untangled\Tests\TempProject;

final class ClassAliasesTest extends TestCase
{
    private ?TempProject $project = null;

    protected function tearDown(): void
    {
        $this->project?->remove();
    }

    public function testNoneHasNoAliases(): void
    {
        self::assertNull(ClassAliases::none()->target('DB'));
    }

    public function testTheLaravelPresetHoldsTheDefaultFacadeAliases(): void
    {
        $aliases = ClassAliases::load(['laravel']);
        self::assertContains('laravel', ClassAliases::presets());
        self::assertSame('Illuminate\\Support\\Facades\\DB', $aliases->target('DB'));
        self::assertSame('Illuminate\\Support\\Facades\\Redirect', $aliases->target('\\Redirect'));
        self::assertSame('Illuminate\\Database\\Eloquent\\Model', $aliases->target('Eloquent'));
        self::assertSame('Illuminate\\Support\\Str', $aliases->target('str'));
        self::assertNull($aliases->target('App\\DB'));
    }

    public function testAFileMapsNamesCaseInsensitivelyAndALaterOneWins(): void
    {
        $this->project = new TempProject([
            'first.json' => ['aliases' => ['DB' => '\\Mine\\Db', 'Money' => 'App\\Money']],
            'second.json' => ['aliases' => ['db' => 'Other\\Db']],
        ]);
        $aliases = ClassAliases::load(['laravel', $this->project->root . '/first.json', $this->project->root . '/second.json']);
        self::assertSame('Other\\Db', $aliases->target('DB'));
        self::assertSame('App\\Money', $aliases->target('MONEY'));
        self::assertSame('Illuminate\\Support\\Facades\\Log', $aliases->target('Log'));
    }

    public function testPackagesDeclareMoreAliasesUnderThePresetsPath(): void
    {
        $packages = [
            new Package('laravel/socialite', [], null, ['laravel' => ['aliases' => ['Socialite' => 'Laravel\\Socialite\\Facades\\Socialite', 'Log' => 'Pkg\\Log']]]),
            new Package('acme/odd', [], null, ['laravel' => ['aliases' => 'not a map']]),
            new Package('acme/bad', [], null, ['laravel' => ['aliases' => ['Bad' => ['x'], 'Not a name' => 'X']]]),
        ];
        $aliases = ClassAliases::load(['laravel'])->withPackages($packages);
        self::assertSame('Laravel\\Socialite\\Facades\\Socialite', $aliases->target('Socialite'));
        self::assertSame('Illuminate\\Support\\Facades\\Log', $aliases->target('Log'), 'a declared alias wins over a package');
        self::assertNull($aliases->target('Bad'));
        self::assertNull(ClassAliases::none()->withPackages($packages)->target('Socialite'), 'only a preset or file that names the path reads packages');
    }

    /** @return iterable<string, array{string|array<mixed>, string}> */
    public static function badFiles(): iterable
    {
        yield 'not JSON' => ['{', 'expected a JSON object with an "aliases" object'];
        yield 'no aliases' => [['DB' => 'X'], 'expected a JSON object with an "aliases" object'];
        yield 'a target that is not a string' => [['aliases' => ['DB' => 1]], '"DB" must map a class name to a class name'];
        yield 'a name that is not a class name' => [['aliases' => ['D B' => 'X']], '"D B" must map a class name to a class name'];
    }

    /** @param string|array<mixed> $contents */
    #[DataProvider('badFiles')]
    public function testABadFileIsAnError(string|array $contents, string $message): void
    {
        $this->project = new TempProject(['aliases.json' => $contents]);
        $this->expectException(\InvalidArgumentException::class);
        $this->expectExceptionMessage($message);
        ClassAliases::load([$this->project->root . '/aliases.json']);
    }

    public function testAMissingFileOrUnknownPresetIsAnError(): void
    {
        $this->expectException(\InvalidArgumentException::class);
        $this->expectExceptionMessage('--aliases=symfony: not a preset (laravel) or a readable file');
        ClassAliases::load(['symfony']);
    }
}
