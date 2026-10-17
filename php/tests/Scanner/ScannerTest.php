<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Scanner;

use PHPUnit\Framework\TestCase;
use Untangled\Scanner\ClassAliases;
use Untangled\Scanner\ScanResult;
use Untangled\Scanner\Scanner;
use Untangled\Tests\TempProject;

/** End-to-end scans of small projects written to a temporary directory. */
final class ScannerTest extends TestCase
{
    private ?TempProject $project = null;

    protected function tearDown(): void
    {
        $this->project?->remove();
    }

    public function testClassNamesResolveCaseInsensitively(): void
    {
        $result = $this->scan([
            'src/Order.php' => '<?php namespace App; class Order { function f(): CUSTOMER {} }',
            'src/Customer.php' => '<?php namespace App; class Customer {}',
        ]);
        self::assertSame(['src/Order.php>src/Customer.php type'], self::edges($result));
    }

    public function testAClassDeclaredTwiceWarnsAndTheFirstFileWins(): void
    {
        $result = $this->scan([
            'src/A.php' => '<?php namespace App; class Dup {}',
            'src/B.php' => '<?php namespace App; class Dup {}',
            'src/User.php' => '<?php namespace App; new Dup();',
        ]);
        self::assertSame(['src/User.php>src/A.php new'], self::edges($result));
        self::assertSame(['src/B.php: App\\Dup is also declared in src/A.php; using the first'], $result->warnings);
    }

    public function testAClassDeclaredTwiceInOneFileDoesNotWarn(): void
    {
        $result = $this->scan(['src/Polyfill.php' => '<?php namespace App; if (PHP_VERSION_ID > 80000) { class P {} } else { class P {} }']);
        self::assertSame([], $result->warnings);
    }

    public function testDeclaredAliasesResolveToTheClassTheyAlias(): void
    {
        $result = $this->scanWith([
            'src/A.php' => '<?php namespace App; use DB; DB::table("x"); \\Redirect::back(); \\Telescope::tag();',
            'vendor/composer/installed.json' => ['packages' => [['name' => 'laravel/framework', 'autoload' => ['psr-4' => ['Illuminate\\' => 'src/Illuminate/']]]]],
        ], ['autoload' => ['psr-4' => ['App\\' => 'src/']]], aliases: ClassAliases::load(['laravel']));
        self::assertSame([
            'src/A.php>composer:laravel/framework import,static',
            'src/A.php>unresolved:class:Telescope static',
        ], self::edges($result));
    }

    public function testAClassThatExistsWinsOverAnAliasOfTheSameName(): void
    {
        $result = $this->scanWith([
            'src/A.php' => '<?php namespace App; \\DB::table("x"); new \\ArrayObject(); \\Gone::x();',
            'src/DB.php' => '<?php class DB {}',
        ], ['autoload' => ['classmap' => ['src/']]], aliases: self::aliases(['DB' => 'Nope\\DB', 'ArrayObject' => 'Nope\\AO', 'Gone' => 'Also\\Gone']));
        self::assertSame([
            'src/A.php>builtin:ArrayObject new',
            'src/A.php>src/DB.php static',
            'src/A.php>unresolved:class:Also\\Gone static',
        ], self::edges($result));
    }

    public function testAnAliasIsNotFollowedFurther(): void
    {
        $result = $this->scanWith(
            ['src/A.php' => '<?php namespace App; \\First::x();', 'src/Real.php' => '<?php namespace App; class Real {}'],
            ['autoload' => ['psr-4' => ['App\\' => 'src/']]],
            aliases: self::aliases(['First' => 'Second', 'Second' => 'App\\Real']),
        );
        self::assertSame(['src/A.php>unresolved:class:Second static'], self::edges($result));
    }

    public function testAFileThatFailsToParseIsStillANode(): void
    {
        $result = $this->scan([
            'src/Broken.php' => '<?php namespace App; class {',
            'src/Ok.php' => '<?php namespace App; class Ok {}',
        ]);
        self::assertSame(['src/Broken.php', 'src/Ok.php'], self::ids($result));
        self::assertCount(1, $result->warnings);
        self::assertStringStartsWith('src/Broken.php: parse error', $result->warnings[0]);
    }

    public function testUnresolvedClassesBecomeUnresolvedNodes(): void
    {
        $result = $this->scan(['src/A.php' => '<?php namespace App; new Missing(); Missing::x();']);
        self::assertSame(['src/A.php>unresolved:class:App\\Missing new,static'], self::edges($result));
        self::assertSame('unresolved', $result->pairs->node('unresolved:class:App\\Missing')['kind']);
    }

    public function testBuiltinsUseTheirCanonicalName(): void
    {
        $result = $this->scan(['src/A.php' => '<?php namespace App; new \\datetimeimmutable(); function f(\\COUNTABLE $c) {}']);
        self::assertSame(['src/A.php>builtin:Countable type', 'src/A.php>builtin:DateTimeImmutable new'], self::edges($result));
    }

    public function testAnImportThatResolvesToNothingIsDropped(): void
    {
        $result = $this->scan(['src/A.php' => '<?php namespace App; use App\\Models; use App\\Gone\\Thing;']);
        self::assertSame([], self::edges($result));
    }

    public function testAnImportOfAProjectClassIsAnEdge(): void
    {
        $result = $this->scan([
            'src/A.php' => '<?php namespace App; use App\\Sub\\B;',
            'src/Sub/B.php' => '<?php namespace App\\Sub; class B {}',
        ]);
        self::assertSame(['src/A.php>src/Sub/B.php import'], self::edges($result));
    }

    public function testFunctionsFallBackToTheGlobalName(): void
    {
        $result = $this->scan(
            [
                'src/A.php' => '<?php namespace App; format_total(); \\App\\local(); strlen("x");',
                'src/helpers.php' => '<?php function format_total() {}',
                'src/local.php' => '<?php namespace App; function local() {}',
            ],
            ['psr-4' => ['App\\' => 'src/'], 'files' => ['src/helpers.php']],
        );
        // strlen is a builtin function and is not recorded.
        self::assertSame(['src/A.php>src/helpers.php call', 'src/A.php>src/local.php call'], self::edges($result));
    }

    public function testFunctionNamesAreCaseInsensitiveButConstantsAreNot(): void
    {
        $result = $this->scan([
            'src/A.php' => '<?php FORMAT_TOTAL(); echo app_version; echo APP_VERSION;',
            'src/helpers.php' => '<?php function format_total() {} const APP_VERSION = 1;',
        ]);
        self::assertSame(['src/A.php>src/helpers.php call,const'], self::edges($result));
        self::assertSame(2, $result->pairs->edges()[0]['count']);
    }

    public function testDefineDeclaresAConstant(): void
    {
        $result = $this->scan([
            'src/A.php' => '<?php echo LEGACY_MODE;',
            'src/boot.php' => '<?php define("LEGACY_MODE", true);',
        ]);
        self::assertSame(['src/A.php>src/boot.php const'], self::edges($result));
    }

    public function testIncludesAreFollowedAndTheTargetIsScanned(): void
    {
        $result = $this->scan(
            [
                'src/A.php' => "<?php require __DIR__ . '/../lib/b.php';",
                'lib/b.php' => "<?php require 'lib/c.php';",
                'lib/c.php' => '<?php',
            ],
            ['psr-4' => ['App\\' => 'src/']],
        );
        self::assertSame(['lib/b.php', 'lib/c.php', 'src/A.php'], self::ids($result));
        self::assertSame(['lib/b.php>lib/c.php include', 'src/A.php>lib/b.php include'], self::edges($result));
    }

    public function testRelativeIncludesTryTheRootThenTheIncludingFile(): void
    {
        $result = $this->scan(
            [
                'src/A.php' => "<?php require 'x.php'; require 'y.php';",
                'x.php' => '<?php',
                'src/x.php' => '<?php',
                'src/y.php' => '<?php',
            ],
            ['classmap' => ['src/A.php']],
        );
        self::assertSame(['src/A.php>src/y.php include', 'src/A.php>x.php include'], self::edges($result));
    }

    public function testIncludeCyclesTerminate(): void
    {
        $result = $this->scan(
            ['a.php' => "<?php require __DIR__ . '/b.php';", 'b.php' => "<?php require __DIR__ . '/a.php';"],
            ['files' => ['a.php']],
        );
        self::assertSame(['a.php>b.php include', 'b.php>a.php include'], self::edges($result));
    }

    public function testIncludesIntoVendorBecomePackages(): void
    {
        $result = $this->scan(
            [
                'src/A.php' => "<?php require __DIR__ . '/../vendor/acme/pdf/src/init.php'; require __DIR__ . '/../vendor/autoload.php';"
                    . " require 'vendor/composer/autoload_real.php'; require 'vendor/stray.php';",
                'vendor/acme/pdf/src/init.php' => '<?php',
                'vendor/autoload.php' => '<?php',
                'vendor/composer/autoload_real.php' => '<?php',
                'vendor/stray.php' => '<?php',
            ],
            ['classmap' => ['src/A.php']],
        );
        // Composer's autoloader is not recorded; a vendor/ file outside any package folder is unresolved.
        self::assertSame(['src/A.php>composer:acme/pdf include', 'src/A.php>unresolved:include:vendor/stray.php include'], self::edges($result));
        self::assertSame(['composer:acme/pdf', 'src/A.php', 'unresolved:include:vendor/stray.php'], self::ids($result));
    }

    public function testIncludesOutsideTheProjectAreUnresolvedWithTheirSourceText(): void
    {
        $result = $this->scan(['src/A.php' => "<?php require '/etc/hostname'; require __DIR__ . '/../../outside.php';"]);
        self::assertSame([
            "src/A.php>unresolved:include:'/etc/hostname' include",
            "src/A.php>unresolved:include:__DIR__ . '/../../outside.php' include",
        ], self::edges($result));
    }

    public function testMissingIncludesInsideTheProjectUseTheirRelativePath(): void
    {
        $result = $this->scan(['src/A.php' => "<?php require __DIR__ . '/gone.php';"]);
        self::assertSame(['src/A.php>unresolved:include:src/gone.php include'], self::edges($result));
    }

    public function testNoAbsolutePathsAppearInTheDocument(): void
    {
        $result = $this->scan(['src/A.php' => "<?php require __DIR__ . '/gone.php'; require __DIR__ . '/../../out.php';"]);
        self::assertStringNotContainsString($this->project->root, $result->pairs->toJson());
    }

    public function testAutoloadDevIsOnlyScannedWithDev(): void
    {
        $files = [
            'src/A.php' => '<?php namespace App; class A {}',
            'tests/ATest.php' => '<?php namespace App\\Tests; new \\App\\A();',
        ];
        $composer = ['autoload' => ['psr-4' => ['App\\' => 'src/']], 'autoload-dev' => ['psr-4' => ['App\\Tests\\' => 'tests/']]];
        self::assertSame(['src/A.php'], self::ids($this->scanWith($files, $composer)));
        $this->project?->remove();
        self::assertSame(['src/A.php', 'tests/ATest.php'], self::ids($this->scanWith($files, $composer, dev: true)));
    }

    public function testScansEveryAutoloadKind(): void
    {
        $result = $this->scan(
            [
                'src/A.php' => '<?php',
                'legacy/Old_Thing.php' => '<?php',
                'classes/Map.inc' => '<?php',
                'classes/Map.txt' => 'not php',
                'single.php' => '<?php',
                'functions.php' => '<?php',
                'not-autoloaded.php' => '<?php',
            ],
            [
                'psr-4' => ['App\\' => 'src/'],
                'psr-0' => ['Old_' => 'legacy/'],
                'classmap' => ['classes/', 'single.php'],
                'files' => ['functions.php', 'missing.php'],
            ],
        );
        self::assertSame(['classes/Map.inc', 'functions.php', 'legacy/Old_Thing.php', 'single.php', 'src/A.php'], self::ids($result));
    }

    public function testPsr4AcceptsAListOfDirectories(): void
    {
        $result = $this->scan(
            ['src/A.php' => '<?php', 'lib/B.php' => '<?php'],
            ['psr-4' => ['App\\' => ['src/', 'lib/']]],
        );
        self::assertSame(['lib/B.php', 'src/A.php'], self::ids($result));
    }

    public function testExcludeFromClassmapIsHonored(): void
    {
        $result = $this->scan(
            ['src/A.php' => '<?php', 'src/Tests/ATest.php' => '<?php', 'src/Deep/Tests/BTest.php' => '<?php', 'src/Fixtures/F.php' => '<?php'],
            ['psr-4' => ['App\\' => 'src/'], 'exclude-from-classmap' => ['src/**/Tests/', '/src/Fixtures/']],
        );
        self::assertSame(['src/A.php', 'src/Tests/ATest.php'], self::ids($result));
    }

    public function testVendorAndHiddenDirectoriesAreNeverScanned(): void
    {
        $result = $this->scan(
            ['A.php' => '<?php', 'vendor/x/y/B.php' => '<?php', '.git/hooks/C.php' => '<?php', 'lib/.cache/D.php' => '<?php'],
            ['classmap' => ['./']],
        );
        self::assertSame(['A.php'], self::ids($result));
    }

    public function testACustomVendorDirIsRespected(): void
    {
        $this->project = new TempProject([
            'composer.json' => ['autoload' => ['classmap' => ['']], 'config' => ['vendor-dir' => 'deps']],
            'A.php' => '<?php new Acme\\Pdf\\Doc();',
            'deps/acme/pdf/src/Doc.php' => '<?php namespace Acme\\Pdf; class Doc {}',
            'deps/composer/installed.json' => ['packages' => [['name' => 'acme/pdf', 'autoload' => ['psr-4' => ['Acme\\Pdf\\' => 'src/']], 'install-path' => '../acme/pdf']]],
        ]);
        $result = (new Scanner())->scan($this->project->root);
        self::assertSame(['A.php'], array_values(array_filter(self::ids($result), static fn (string $id): bool => !str_contains($id, ':'))));
        self::assertSame(['A.php>composer:acme/pdf new'], self::edges($result));
    }

    public function testComposerLockIsUsedWithoutVendor(): void
    {
        $result = $this->scan(
            [
                'src/A.php' => '<?php namespace App; use Monolog\\Logger; new Logger(); new \\Acme\\Dev\\Thing(); new \\Twig_Environment();',
                'composer.lock' => [
                    'packages' => [
                        ['name' => 'monolog/monolog', 'autoload' => ['psr-4' => ['Monolog\\' => 'src/Monolog']]],
                        ['name' => 'twig/twig', 'autoload' => ['psr-0' => ['Twig_' => 'lib/']]],
                    ],
                    'packages-dev' => [['name' => 'acme/dev', 'autoload' => ['psr-4' => ['Acme\\Dev\\' => 'src/']]]],
                ],
            ],
        );
        self::assertSame([
            'src/A.php>composer:acme/dev new',
            'src/A.php>composer:monolog/monolog import,new',
            'src/A.php>composer:twig/twig new',
        ], self::edges($result));
    }

    public function testTheLongestVendorPrefixWins(): void
    {
        $result = $this->scan([
            'src/A.php' => '<?php new \\Acme\\Core\\X(); new \\Acme\\Other\\Y();',
            'composer.lock' => ['packages' => [
                ['name' => 'acme/all', 'autoload' => ['psr-4' => ['Acme\\' => 'src/']]],
                ['name' => 'acme/core', 'autoload' => ['psr-4' => ['Acme\\Core\\' => 'src/']]],
            ]],
        ]);
        self::assertSame(['src/A.php>composer:acme/all new', 'src/A.php>composer:acme/core new'], self::edges($result));
    }

    public function testAnEmptyCatchAllPrefixIsIgnored(): void
    {
        $result = $this->scan([
            'src/A.php' => '<?php new \\Anything\\At\\All();',
            'composer.lock' => ['packages' => [['name' => 'greedy/pkg', 'autoload' => ['psr-4' => ['' => 'src/']]]]],
        ]);
        self::assertSame(['src/A.php>unresolved:class:Anything\\At\\All new'], self::edges($result));
    }

    public function testProjectClassesWinOverVendorPrefixes(): void
    {
        $result = $this->scan([
            'src/Logger.php' => '<?php namespace Monolog; class Logger {}',
            'src/A.php' => '<?php new \\Monolog\\Logger();',
            'composer.lock' => ['packages' => [['name' => 'monolog/monolog', 'autoload' => ['psr-4' => ['Monolog\\' => 'src/']]]]],
        ], ['classmap' => ['src/']]);
        self::assertSame(['src/A.php>src/Logger.php new'], self::edges($result));
    }

    public function testSymbolsAndModulesAreRecorded(): void
    {
        // A class and a constant with the same name are one symbol.
        $result = $this->scan(['src/A.php' => '<?php namespace App; class A {} function a() {} const A = 1; const B = 2;']);
        self::assertSame(
            ['id' => 'src/A.php', 'kind' => 'internal', 'module' => 'App', 'symbols' => ['App\\A', 'App\\B', 'App\\a']],
            $result->pairs->node('src/A.php'),
        );
    }

    public function testBuiltinsWinOverPolyfillPackages(): void
    {
        $result = $this->scanWith(
            [
                'src/A.php' => '<?php namespace App; class A implements \Stringable { function __toString(): string { return ""; } }',
                'vendor/composer/installed.json' => ['packages' => [
                    ['name' => 'acme/polyfill', 'autoload' => ['classmap' => ['stubs/']], 'install-path' => '../acme/polyfill'],
                ]],
                'vendor/acme/polyfill/stubs/Stringable.php' => '<?php if (PHP_VERSION_ID < 80000) { interface Stringable {} }',
            ],
            ['autoload' => ['psr-4' => ['App\\' => 'src/']]],
        );
        self::assertSame(['src/A.php>builtin:Stringable implements'], self::edges($result));
    }

    public function testComposerRuntimeClassesAreTheRuntimeApi(): void
    {
        $result = $this->scan(['src/A.php' => '<?php namespace App; use Composer\InstalledVersions; InstalledVersions::getVersion("x"); new \Composer\Autoload\ClassLoader();']);
        self::assertSame(['src/A.php>composer:composer-runtime-api import,new,static'], self::edges($result));
    }

    public function testSourcesAddCodeOutsideAutoload(): void
    {
        $result = $this->scanWith(
            [
                'src/A.php' => '<?php namespace App; new \Legacy_Order(); require_once "Legacy/helpers.php";',
                'lib/Legacy/Order.php' => '<?php class Legacy_Order {}',
                'lib/Legacy/helpers.php' => '<?php function legacy() {}',
                'lib/Legacy/Old.inc' => '<?php class Legacy_Old extends Legacy_Order {}',
            ],
            ['autoload' => ['psr-4' => ['App\\' => 'src/']]],
            sources: ['lib'],
        );
        // The include is found through the lib folder, as include_path would find it.
        self::assertSame([
            'lib/Legacy/Old.inc>lib/Legacy/Order.php extends',
            'src/A.php>lib/Legacy/Order.php new',
            'src/A.php>lib/Legacy/helpers.php include',
        ], self::edges($result));
        self::assertSame([], $result->warnings);
    }

    public function testAMissingSourceWarns(): void
    {
        $result = $this->scanWith(['src/A.php' => '<?php namespace App;'], ['autoload' => ['psr-4' => ['App\\' => 'src/']]], sources: ['nope']);
        self::assertSame(['--source=nope: no such file or folder in the project'], $result->warnings);
    }

    public function testFilesOutsideAutoloadAreCountedInAWarning(): void
    {
        $result = $this->scanWith(
            [
                'src/A.php' => '<?php namespace App;',
                'src/Tests/ATest.php' => '<?php',
                'tests/BTest.php' => '<?php',
                'config/app.php' => '<?php',
                'config/db.php' => '<?php',
                'database/migrations/1.php' => '<?php',
                'index.php' => '<?php',
                'node_modules/x/y.php' => '<?php',
                '.git/hooks/z.php' => '<?php',
            ],
            [
                'autoload' => ['psr-4' => ['App\\' => 'src/'], 'exclude-from-classmap' => ['**/Tests/']],
                'autoload-dev' => ['psr-4' => ['App\\Tests\\' => 'tests/']],
            ],
        );
        self::assertSame(
            ['4 PHP files are not covered by composer.json autoload rules and were not scanned (config/ 2, (project root) 1, database/migrations/ 1);'
                . ' add folders with --source=<folder> if they hold code you want analyzed'],
            $result->warnings,
        );
    }

    public function testTheUncoveredWarningNamesTheDeepestFolderEachTopFolderShares(): void
    {
        $result = $this->scan([
            'src/A.php' => '<?php namespace App;',
            'lang/en/a.php' => '<?php',
            'lang/fr/a.php' => '<?php',
            'app/code/core/X.php' => '<?php',
            'app/code/local/Y.php' => '<?php',
        ]);
        self::assertSame(
            ['4 PHP files are not covered by composer.json autoload rules and were not scanned (app/code/ 2, lang/ 2);'
                . ' add folders with --source=<folder> if they hold code you want analyzed'],
            $result->warnings,
        );
    }

    public function testTheUncoveredWarningNamesFiveFoldersAtMost(): void
    {
        $files = ['src/A.php' => '<?php namespace App;'];
        foreach (range(1, 7) as $n) {
            $files["f{$n}/x.php"] = '<?php';
        }
        $files['f1/y.php'] = '<?php';
        $result = $this->scan($files);
        self::assertSame(
            ['8 PHP files are not covered by composer.json autoload rules and were not scanned (f1/ 2, f2/ 1, f3/ 1, f4/ 1, f5/ 1, and 2 more);'
                . ' add folders with --source=<folder> if they hold code you want analyzed'],
            $result->warnings,
        );
    }

    public function testMissingPackageListsWarn(): void
    {
        $result = $this->scanWith(['src/A.php' => '<?php namespace App;'], ['require' => ['php' => '^8.2', 'acme/x' => '^1.0'], 'autoload' => ['psr-4' => ['App\\' => 'src/']]]);
        self::assertCount(1, $result->warnings);
        self::assertStringStartsWith('no vendor/composer/installed.json or composer.lock', $result->warnings[0]);

        $result = $this->scanWith(['src/A.php' => '<?php namespace App;'], ['require' => ['php' => '^8.2', 'ext-json' => '*'], 'autoload' => ['psr-4' => ['App\\' => 'src/']]]);
        self::assertSame([], $result->warnings);
    }

    public function testLatin1NamesAreWrittenAsUtf8(): void
    {
        $result = $this->scan([
            'src/Cafe.php' => "<?php namespace App; class Caf\xe9 {}",
            'src/A.php' => "<?php namespace App; new Caf\xe9(); new Cr\xe8me();",
        ]);
        self::assertSame(['src/A.php>src/Cafe.php new', "src/A.php>unresolved:class:App\\Crème new"], self::edges($result));
        self::assertSame(['App\\Café'], $result->pairs->node('src/Cafe.php')['symbols']);
        self::assertJson($result->pairs->toJson());
    }

    public function testAnEmptyAutoloadGivesAnEmptyDocument(): void
    {
        $this->project = new TempProject(['composer.json' => ['name' => 'x/y']]);
        $result = (new Scanner())->scan($this->project->root);
        self::assertSame([], $result->pairs->nodes());
        self::assertSame([], $result->warnings);
    }

    /**
     * @param array<string, string|array<mixed>> $files
     * @param array<string, mixed> $autoload defaults to psr-4 App\ => src/
     */
    private function scan(array $files, array $autoload = ['psr-4' => ['App\\' => 'src/']]): ScanResult
    {
        return $this->scanWith($files, ['autoload' => $autoload]);
    }

    /**
     * @param array<string, string|array<mixed>> $files
     * @param array<string, mixed> $composer
     */
    /** @param list<string> $sources */
    private function scanWith(array $files, array $composer, bool $dev = false, array $sources = [], ?ClassAliases $aliases = null): ScanResult
    {
        $this->project = new TempProject(['composer.json' => $composer] + $files);
        return (new Scanner(dev: $dev, sources: $sources, aliases: $aliases))->scan($this->project->root);
    }

    /** @param array<string, string> $map */
    private static function aliases(array $map): ClassAliases
    {
        $file = tempnam(sys_get_temp_dir(), 'untangled-aliases');
        file_put_contents($file, json_encode(['aliases' => $map]));
        try {
            return ClassAliases::load([$file]);
        } finally {
            unlink($file);
        }
    }

    /** @return list<string> */
    private static function ids(ScanResult $result): array
    {
        return array_column($result->pairs->nodes(), 'id');
    }

    /** @return list<string> "from>to kind,kind" */
    private static function edges(ScanResult $result): array
    {
        return array_map(static fn (array $e): string => "{$e['from']}>{$e['to']} " . implode(',', $e['kinds']), $result->pairs->edges());
    }
}
