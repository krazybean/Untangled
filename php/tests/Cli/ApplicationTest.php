<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Cli;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Untangled\Cli\Application;
use Untangled\Tests\ConformanceTest;
use Untangled\Tests\TempProject;
use Untangled\Version;

final class ApplicationTest extends TestCase
{
    private const CASES = __DIR__ . '/../../../conformance/cases';

    private ?TempProject $project = null;

    protected function tearDown(): void
    {
        $this->project?->remove();
    }

    public function testHelp(): void
    {
        foreach (['-h', '--help'] as $flag) {
            [$code, $out] = self::cli([$flag]);
            self::assertSame(0, $code);
            self::assertStringStartsWith('Usage: untangled scan', $out);
            self::assertStringContainsString('untangled analyze', $out);
        }
    }

    public function testVersion(): void
    {
        foreach (['-V', '--version'] as $flag) {
            self::assertSame([0, Version::NAME . ' ' . Version::VERSION . "\n", ''], self::cli([$flag]));
        }
    }

    public function testNoCommandPrintsUsage(): void
    {
        [$code, $out, $err] = self::cli([]);
        self::assertSame(2, $code);
        self::assertSame('', $out);
        self::assertStringStartsWith('Usage:', $err);
    }

    public function testUnknownCommand(): void
    {
        [$code, , $err] = self::cli(['frobnicate']);
        self::assertSame(2, $code);
        self::assertStringStartsWith('Unknown command: frobnicate', $err);
    }

    /** @return iterable<string, array{list<string>, string}> */
    public static function badOptions(): iterable
    {
        yield 'scan rejects analyze options' => [['scan', '.', '--cluster=namespace:1'], 'Unknown option for scan: --cluster'];
        yield 'analyze rejects scan options' => [['analyze', '.', '--format=snakefood'], 'Unknown option for analyze: --format'];
        yield 'unknown option' => [['scan', '.', '--nope'], 'Unknown option for scan: --nope'];
        yield 'unknown format' => [['scan', '.', '--format=xml'], 'Unknown format: xml'];
        yield 'option without a value' => [['analyze', '.', '--cluster'], 'Option --cluster needs a value'];
        yield 'output without a value' => [['scan', '.', '--output'], 'Option --output needs a value'];
        yield 'analyze rejects report options' => [['analyze', '.', '--title=x'], 'Unknown option for analyze: --title'];
        yield 'report rejects scan options' => [['report', '.', '--dev', '--format=snakefood'], 'Unknown format: snakefood'];
        yield 'report rejects an unknown format' => [['report', '.', '--format=json'], 'Unknown format: json'];
        yield 'unknown clustering' => [['analyze', '.', '--cluster=files:2'], 'unknown clustering "files:2"'];
        yield 'malformed rules' => [['analyze', '.', '--cluster=rules:' . __DIR__ . '/../../composer.json'], 'must be "<prefix> <cluster>"'];
    }

    /** @param list<string> $args */
    #[DataProvider('badOptions')]
    public function testBadOptionsExitWithTwo(array $args, string $message): void
    {
        [$code, $out, $err] = self::cli($args);
        self::assertSame(2, $code);
        self::assertSame('', $out);
        self::assertStringContainsString($message, $err);
    }

    public function testScanRefusesADirectoryWithoutComposerJson(): void
    {
        $this->project = new TempProject(['a.php' => '<?php']);
        [$code, $out, $err] = self::cli(['scan', $this->project->root]);
        self::assertSame(1, $code);
        self::assertSame('', $out);
        self::assertStringStartsWith('error: No composer.json', $err);
    }

    public function testScanWritesThePairsDocument(): void
    {
        $case = self::CASES . '/three-cycle/php';
        [$code, $out, $err] = self::cli(['scan', $case . '/project']);
        self::assertSame(0, $code);
        self::assertSame('', $err);
        ConformanceTest::assertSameDocument(ConformanceTest::read($case . '/expected/pairs.json'), json_decode($out, true));
    }

    public function testScanSnakefood(): void
    {
        [$code, $out] = self::cli(['scan', self::CASES . '/three-cycle/php/project', '--format=snakefood']);
        self::assertSame(0, $code);
        self::assertStringContainsString("'src/Catalog.php'), (None, None))", $out);
        self::assertCount(5, explode("\n", trim($out)));
    }

    public function testScanDev(): void
    {
        $this->project = new TempProject([
            'composer.json' => ['autoload' => ['psr-4' => ['App\\' => 'src/']], 'autoload-dev' => ['psr-4' => ['T\\' => 'tests/']]],
            'src/A.php' => '<?php',
            'tests/B.php' => '<?php',
        ]);
        [, $out] = self::cli(['scan', $this->project->root]);
        self::assertStringNotContainsString('tests/B.php', $out);
        [, $out] = self::cli(['scan', $this->project->root, '--dev']);
        self::assertStringContainsString('tests/B.php', $out);
    }

    public function testSourceAddsFoldersToScan(): void
    {
        $this->project = new TempProject([
            'composer.json' => ['autoload' => ['psr-4' => ['App\\' => 'src/']]],
            'src/A.php' => '<?php namespace App; new \\Legacy();',
            'lib/Legacy.php' => '<?php class Legacy {}',
            'routes/web.php' => '<?php',
        ]);
        [, $out, $err] = self::cli(['scan', $this->project->root]);
        self::assertStringNotContainsString('lib/Legacy.php', $out);
        self::assertStringContainsString('2 PHP files are not covered', $err);
        foreach (['scan', 'analyze', 'report'] as $command) {
            [$code, $out, $err] = self::cli([$command, $this->project->root, '--source=lib', '--source=routes']);
            self::assertSame(0, $code, $command);
            self::assertStringContainsString('lib/Legacy.php', $out, $command);
            self::assertStringContainsString('routes/web.php', $out, $command);
            self::assertSame('', $err, $command);
        }
    }

    public function testAliasesResolveGlobalClassAliases(): void
    {
        $this->project = new TempProject([
            'composer.json' => ['autoload' => ['psr-4' => ['App\\' => 'src/']]],
            'src/A.php' => '<?php namespace App; \\DB::table("x"); \\Money::sum();',
            'src/Money.php' => '<?php namespace App; class Money {}',
            'aliases.json' => ['aliases' => ['Money' => 'App\\Money']],
            'vendor/composer/installed.json' => ['packages' => [['name' => 'laravel/framework', 'autoload' => ['psr-4' => ['Illuminate\\' => 'src/']]]]],
        ]);
        [, $out] = self::cli(['scan', $this->project->root]);
        self::assertStringContainsString('unresolved:class:DB', $out);
        foreach (['scan', 'analyze', 'report'] as $command) {
            $args = [$command, $this->project->root, '--aliases=laravel', '--aliases=' . $this->project->root . '/aliases.json'];
            [$code, $out, $err] = self::cli($command === 'report' ? [...$args, '--format=dot'] : $args);
            self::assertSame(0, $code, $command);
            self::assertSame('', $err, $command);
            self::assertStringNotContainsString($command === 'analyze' ? '"unresolved": 1' : 'unresolved:', $out, $command);
        }
    }

    public function testAliasesThatCannotBeReadAreAnError(): void
    {
        [$code, $out, $err] = self::cli(['scan', '.', '--aliases=/no/such.json']);
        self::assertSame(1, $code);
        self::assertSame('', $out);
        self::assertStringStartsWith('error: --aliases=/no/such.json: not a preset (laravel) or a readable file', $err);
    }

    public function testScanWarningsGoToStandardError(): void
    {
        $this->project = new TempProject(['composer.json' => ['autoload' => ['classmap' => ['src/']]], 'src/Broken.php' => '<?php class {']);
        [$code, $out, $err] = self::cli(['scan', $this->project->root]);
        self::assertSame(0, $code);
        self::assertStringStartsWith('warning: src/Broken.php: parse error', $err);
        self::assertStringContainsString('"src/Broken.php"', $out);
    }

    public function testOutputWritesAFile(): void
    {
        $this->project = new TempProject(['composer.json' => []]);
        $file = $this->project->root . '/out.json';
        [$code, $out] = self::cli(['analyze', self::CASES . '/three-cycle/php/project', '--output=' . $file]);
        self::assertSame(0, $code);
        self::assertSame('', $out);
        ConformanceTest::assertSameDocument(ConformanceTest::read(self::CASES . '/three-cycle/php/expected/analysis.json'), ConformanceTest::read($file));
    }

    public function testOutputToAnUnwritablePathFails(): void
    {
        [$code, , $err] = self::cli(['scan', self::CASES . '/three-cycle/php/project', '--output=/no/such/dir/out.json']);
        self::assertSame(1, $code);
        self::assertStringContainsString('error: cannot write /no/such/dir/out.json', $err);
    }

    public function testAnalyzeAProject(): void
    {
        $layers = self::CASES . '/layers/php';
        [$code, $out, $err] = self::cli(['analyze', $layers . '/project', '--cluster=namespace:2']);
        self::assertSame(0, $code);
        self::assertSame('', $err);
        ConformanceTest::assertSameDocument(ConformanceTest::read($layers . '/expected/analysis.namespace-2.json'), json_decode($out, true));
        self::assertStringEndsWith("}\n", $out);
    }

    public function testAnalyzeAPairsDocumentWithRules(): void
    {
        $layers = self::CASES . '/layers/php';
        [$code, $out] = self::cli(['analyze', $layers . '/expected/pairs.json', '--cluster=rules:' . $layers . '/clusters.rules']);
        self::assertSame(0, $code);
        ConformanceTest::assertSameDocument(ConformanceTest::read($layers . '/expected/analysis.rules.json'), json_decode($out, true));
    }

    public function testUnmatchedNodesWarnAndStillWriteTheOutput(): void
    {
        $layers = self::CASES . '/layers/php';
        [$code, $out, $err] = self::cli(['analyze', $layers . '/expected/pairs.json', '--cluster=rules:' . self::rulesFile("src/Domain/ Core\n")]);
        self::assertSame(0, $code);
        self::assertStringStartsWith('warning: rules: ', $err);
        self::assertStringContainsString("5 files match no rule and each becomes its own cluster: bootstrap.php, src/Http/Router.php", $err);
        self::assertSame('rules', json_decode($out, true)['clustering']);
    }

    public function testNoWarningWhenEveryNodeMatches(): void
    {
        $layers = self::CASES . '/layers/php';
        [$code, , $err] = self::cli(['analyze', $layers . '/expected/pairs.json', '--cluster=rules:' . self::rulesFile("src/ Core\nbootstrap.php Boot\n"), '--strict']);
        self::assertSame(0, $code);
        self::assertSame('', $err);
    }

    public function testStrictFailsOnUnmatchedNodesAndWritesNothing(): void
    {
        $layers = self::CASES . '/layers/php';
        foreach (['analyze', 'report'] as $command) {
            [$code, $out, $err] = self::cli([$command, $layers . '/expected/pairs.json', '--cluster=rules:' . self::rulesFile("src/Domain/ Core\n"), '--strict']);
            self::assertSame(1, $code, $command);
            self::assertSame('', $out, $command);
            self::assertStringStartsWith('error: rules: ', $err);
            self::assertStringNotContainsString('warning:', $err);
        }
    }

    public function testUnmatchedNodesAreCountedAfterFiltering(): void
    {
        $layers = self::CASES . '/layers/php';
        [$code, , $err] = self::cli(['analyze', $layers . '/expected/pairs.json', '--cluster=rules:' . self::rulesFile("src/Domain/ Core\n"), '--exclude=src/Http/**', '--exclude=src/Infra/**', '--exclude=bootstrap.php', '--strict']);
        self::assertSame(0, $code);
        self::assertSame('', $err);
    }

    public function testStrictNeedsRulesClustering(): void
    {
        foreach ([['analyze', '.', '--strict'], ['analyze', '.', '--cluster=folder:1', '--strict'], ['report', '.', '--strict']] as $args) {
            [$code, , $err] = self::cli($args);
            self::assertSame(2, $code);
            self::assertStringContainsString('--strict only applies to --cluster=rules:<file>', $err);
        }
        [$code, , $err] = self::cli(['analyze', '.', '--cluster=rules:x', '--strict=yes']);
        self::assertSame(2, $code);
        self::assertStringContainsString('--strict takes no value', $err);
        [$code, , $err] = self::cli(['scan', '.', '--strict']);
        self::assertSame(2, $code);
        self::assertStringContainsString('Unknown option for scan: --strict', $err);
    }

    public function testDependentsOfAFileInAPairsDocument(): void
    {
        $pairs = self::CASES . '/layers/php/expected/pairs.json';
        [$code, $out, $err] = self::cli(['dependents', $pairs, 'src/Domain/User.php']);
        self::assertSame(0, $code);
        self::assertSame('', $err);
        self::assertSame("2 dependents of src/Domain/User.php\n\nsrc/Domain/\n  Order.php\n\nsrc/Infra/\n  UserRepository.php\n", $out);
    }

    public function testDependentsScansAProject(): void
    {
        [$code, $out] = self::cli(['dependents', self::CASES . '/layers/php/project', 'App\\Domain\\User', '--format=json']);
        self::assertSame(0, $code);
        self::assertSame(['src/Domain/Order.php', 'src/Infra/UserRepository.php'], array_column(json_decode($out, true)['dependents'], 'id'));
    }

    public function testDependentsTakesTheCurrentFolderWhenTheFirstArgumentIsATarget(): void
    {
        $project = self::CASES . '/layers/php/project';
        $previous = getcwd();
        chdir($project);
        try {
            [$code, $out] = self::cli(['dependents', 'App\\Domain\\User', '--format=json']);
        } finally {
            chdir($previous);
        }
        self::assertSame(0, $code);
        self::assertSame(['src/Domain/Order.php', 'src/Infra/UserRepository.php'], array_column(json_decode($out, true)['dependents'], 'id'));
    }

    public function testDependentsWritesToAFile(): void
    {
        $file = tempnam(sys_get_temp_dir(), 'untangled-dependents');
        [$code, $out] = self::cli(['dependents', self::CASES . '/layers/php/expected/pairs.json', 'src/Domain/User.php', '--format=json', '--output=' . $file]);
        self::assertSame([0, ''], [$code, $out]);
        self::assertSame('untangled-dependents', json_decode((string) file_get_contents($file), true)['format']);
        unlink($file);
    }

    public function testDependentsFailsOnAnUnknownTarget(): void
    {
        [$code, $out, $err] = self::cli(['dependents', self::CASES . '/layers/php/expected/pairs.json', 'src/Nope.php']);
        self::assertSame([1, ''], [$code, $out]);
        self::assertSame("error: no node or symbol \"src/Nope.php\" in the pairs document\n", $err);
    }

    public function testDependentsRefusesAClusteredDocument(): void
    {
        $file = tempnam(sys_get_temp_dir(), 'untangled-clustered');
        file_put_contents($file . '.json', json_encode(['format' => 'untangled-pairs', 'version' => '0.1', 'language' => 'php', 'nodes' => [['id' => 'Core', 'kind' => 'cluster', 'members' => ['a.php']]], 'edges' => []]));
        [$code, , $err] = self::cli(['dependents', $file . '.json', 'Core']);
        unlink($file);
        unlink($file . '.json');
        self::assertSame(1, $code);
        self::assertStringContainsString('already clustered', $err);
    }

    public function testDependentsUsageErrors(): void
    {
        $pairs = self::CASES . '/layers/php/expected/pairs.json';
        foreach ([
            [['dependents', $pairs], 'dependents needs at least one file or symbol'],
            [['dependents', $pairs, 'src/Domain/User.php', '--format=html'], 'Unknown format: html'],
            [['dependents', $pairs, 'src/Domain/User.php', '--transitive=yes'], 'Option --transitive takes no value'],
            [['dependents', $pairs, 'src/Domain/User.php', '--cluster=folder:1'], 'Unknown option for dependents: --cluster'],
            [['analyze', $pairs, '--transitive'], 'Unknown option for analyze: --transitive'],
        ] as [$args, $message]) {
            [$code, , $err] = self::cli($args);
            self::assertSame(2, $code, $message);
            self::assertStringContainsString($message, $err);
        }
    }

    public function testDependentsMaxDepthAndThrough(): void
    {
        $pairs = self::CASES . '/layers/php/expected/pairs.json';
        $ids = static fn (array $args): array => array_column(json_decode(self::cli(['dependents', $pairs, '--format=json', ...$args])[1], true)['dependents'], 'id');
        self::assertSame(['src/Domain/Order.php', 'src/Infra/UserRepository.php', 'src/Http/UserController.php'], $ids(['--transitive', '--max-depth=2', 'src/Domain/User.php']));
        self::assertSame(['src/Domain/Order.php'], $ids(['--transitive', '--through=src/Domain/**', 'src/Domain/User.php']));
        self::assertSame(
            ['src/Domain/Order.php', 'src/Http/UserController.php'],
            $ids(['--transitive', '--through=src/Domain/**', '--through=src/Http/**', '--max-depth=2', 'src/Domain/User.php']),
        );
    }

    public function testDependentsMaxDepthUsageErrors(): void
    {
        $pairs = self::CASES . '/layers/php/expected/pairs.json';
        foreach ([
            [['--transitive', '--max-depth=0'], 'Option --max-depth needs a positive integer, as in --max-depth=2 (got "0")'],
            [['--transitive', '--max-depth=-1'], '(got "-1")'],
            [['--transitive', '--max-depth=2.5'], '(got "2.5")'],
            [['--transitive', '--max-depth=02'], '(got "02")'],
            [['--transitive', '--max-depth=two'], '(got "two")'],
            [['--transitive', '--max-depth='], '(got "")'],
            [['--max-depth=2'], '--max-depth only applies with --transitive'],
            [['--transitive', '--max-depth'], 'Option --max-depth needs a value'],
            [['--through'], 'Option --through needs a value'],
        ] as [$args, $message]) {
            [$code, $out, $err] = self::cli(['dependents', $pairs, 'src/Domain/User.php', ...$args]);
            self::assertSame(2, $code, $message);
            self::assertSame('', $out);
            self::assertStringContainsString($message, $err);
        }
        [$code, , $err] = self::cli(['analyze', $pairs, '--through=src/**']);
        self::assertSame(2, $code);
        self::assertStringContainsString('Unknown option for analyze: --through', $err);
    }

    public function testDependentsAcceptsAHugeMaxDepth(): void
    {
        $pairs = self::CASES . '/layers/php/expected/pairs.json';
        [$code, $out] = self::cli(['dependents', $pairs, 'src/Domain/User.php', '--transitive', '--max-depth=99999999999999999999', '--format=json']);
        self::assertSame(0, $code);
        self::assertCount(5, json_decode($out, true)['dependents']);
    }

    public function testDependentsAcceptsAnAbsolutePathInsideTheProject(): void
    {
        $project = (string) realpath(self::CASES . '/layers/php/project');
        $ids = static fn (array $args): array => array_column(json_decode(self::cli(['dependents', ...$args, '--format=json'])[1], true)['dependents'], 'id');
        $expected = ['src/Domain/Order.php', 'src/Infra/UserRepository.php'];
        self::assertSame($expected, $ids([$project, $project . '/src/Domain/User.php']));
        self::assertSame($expected, $ids([$project, str_replace('/', DIRECTORY_SEPARATOR, $project) . DIRECTORY_SEPARATOR . 'src' . DIRECTORY_SEPARATOR . 'Domain' . DIRECTORY_SEPARATOR . 'User.php']));
        // With a saved pairs document, the project is the current folder.
        $previous = getcwd();
        chdir($project);
        try {
            self::assertSame($expected, $ids([self::CASES . '/layers/php/expected/pairs.json', $project . '/src/Domain/User.php']));
        } finally {
            chdir($previous);
        }
    }

    public function testDependentsRefusesAnAbsolutePathOutsideTheProject(): void
    {
        $project = (string) realpath(self::CASES . '/layers/php/project');
        [$code, $out, $err] = self::cli(['dependents', $project, dirname($project) . '/src/Domain/User.php']);
        self::assertSame(1, $code);
        self::assertSame('', $out);
        self::assertStringContainsString('is outside the project folder', $err);
    }

    public function testDependentsAcceptsAClassNameWithALeadingBackslash(): void
    {
        [$code, $out] = self::cli(['dependents', self::CASES . '/layers/php/expected/pairs.json', '\\App\\Domain\\User', '--format=json']);
        self::assertSame(0, $code);
        self::assertSame(['src/Domain/Order.php', 'src/Infra/UserRepository.php'], array_column(json_decode($out, true)['dependents'], 'id'));
    }

    public function testAnalyzeAppliesIncludeAndExcludeInOrder(): void
    {
        $project = self::CASES . '/layers/php/project';
        $ids = static fn (array $args): array => array_column(json_decode(self::cli(['analyze', $project, ...$args])[1], true)['units'], 'id');

        $kept = $ids(['--exclude=src/Http/**', '--include=src/Http/Router.php']);
        self::assertContains('src/Http/Router.php', $kept);
        self::assertNotContains('src/Http/UserController.php', $kept);

        $reversed = $ids(['--include=src/Http/Router.php', '--exclude=src/Http/**']);
        self::assertNotContains('src/Http/Router.php', $reversed);
    }

    public function testAnalyzeAMissingRulesFile(): void
    {
        [$code, , $err] = self::cli(['analyze', '.', '--cluster=rules:/no/such.rules']);
        self::assertSame(1, $code);
        self::assertStringContainsString('cannot read rules file /no/such.rules', $err);
    }

    public function testAnalyzeAFileThatIsNotJson(): void
    {
        [$code, , $err] = self::cli(['analyze', __FILE__]);
        self::assertSame(1, $code);
        self::assertStringContainsString('not valid JSON', $err);
    }

    public function testAnalyzeADocumentOfAnotherFormat(): void
    {
        [$code, , $err] = self::cli(['analyze', self::CASES . '/three-cycle/php/expected/analysis.json']);
        self::assertSame(1, $code);
        self::assertStringContainsString('not an Untangled pairs document', $err);
    }

    public function testAnalyzeWarnsOnAnUnknownMinorVersion(): void
    {
        $doc = ConformanceTest::read(self::CASES . '/three-cycle/php/expected/pairs.json');
        $doc['version'] = '0.9';
        $this->project = new TempProject(['pairs.json' => $doc]);
        [$code, $out, $err] = self::cli(['analyze', $this->project->root . '/pairs.json']);
        self::assertSame(0, $code);
        self::assertStringStartsWith('warning: pairs document version 0.9', $err);
        self::assertSame(1, json_decode($out, true)['summary']['cycles']);
    }

    public function testAnalyzeRefusesAClusteredDocument(): void
    {
        $this->project = new TempProject(['pairs.json' => [
            'format' => 'untangled-pairs', 'version' => Version::SPEC, 'language' => 'php',
            'nodes' => [['id' => 'App', 'kind' => 'cluster', 'members' => ['a.php']]], 'edges' => [],
        ]]);
        [$code, , $err] = self::cli(['analyze', $this->project->root . '/pairs.json']);
        self::assertSame(1, $code);
        self::assertStringContainsString('already clustered', $err);
    }

    public function testReportDot(): void
    {
        $layers = self::CASES . '/layers/php';
        [$code, $out, $err] = self::cli(['report', $layers . '/project', '--format=dot', '--cluster=namespace:2']);
        self::assertSame(0, $code);
        self::assertSame('', $err);
        self::assertSame(file_get_contents($layers . '/expected/graph.namespace-2.dot'), $out);
    }

    public function testReportClassicStyle(): void
    {
        [$code, $out, $err] = self::cli(['report', self::CASES . '/layers/php/project', '--format=dot', '--style=classic']);
        self::assertSame(0, $code);
        self::assertSame('', $err);
        self::assertStringContainsString('node [shape=ellipse, style=filled, fillcolor=lightgrey', $out);
        self::assertStringNotContainsString('#d03b3b', $out);
    }

    public function testReportStyleNeedsDotAndAKnownName(): void
    {
        $project = self::CASES . '/layers/php/project';
        [$code, , $err] = self::cli(['report', $project, '--format=dot', '--style=pastel']);
        self::assertSame(2, $code);
        self::assertStringContainsString('Unknown style: pastel', $err);
        [$code, , $err] = self::cli(['report', $project, '--style=classic']);
        self::assertSame(2, $code);
        self::assertStringContainsString('--style only applies to --format=dot', $err);
    }

    public function testReportDefaultsToHtmlTitledByThePackageName(): void
    {
        [$code, $out] = self::cli(['report', self::CASES . '/layers/php/project']);
        self::assertSame(0, $code);
        self::assertStringStartsWith('<!doctype html>', $out);
        self::assertStringContainsString('<h1>untangled-fixtures/layers</h1>', $out);
    }

    public function testReportTitleFallsBackToTheFolderName(): void
    {
        $this->project = new TempProject(['composer.json' => ['autoload' => ['classmap' => ['a.php']]], 'a.php' => '<?php']);
        [, $out] = self::cli(['report', $this->project->root]);
        self::assertStringContainsString('<h1>' . basename($this->project->root) . '</h1>', $out);
    }

    public function testReportReadsAPairsDocumentAndTakesATitle(): void
    {
        $pairs = self::CASES . '/layers/php/expected/pairs.json';
        [$code, $out] = self::cli(['report', $pairs, '--title=Layers & co']);
        self::assertSame(0, $code);
        self::assertStringContainsString('<h1>Layers &amp; co</h1>', $out);
        [, $out] = self::cli(['report', $pairs]);
        self::assertStringContainsString('<h1>pairs.json</h1>', $out);
    }

    public function testReportAppliesFilters(): void
    {
        [, $out] = self::cli(['report', self::CASES . '/layers/php/project', '--format=dot', '--exclude=src/Http/**']);
        self::assertStringNotContainsString('src/Http/', $out);
        self::assertStringContainsString('"src/Domain/User.php"', $out);
    }

    public function testReportWritesAFile(): void
    {
        $this->project = new TempProject(['composer.json' => []]);
        $file = $this->project->root . '/report.html';
        [$code, $out] = self::cli(['report', self::CASES . '/three-cycle/php/project', '--output=' . $file]);
        self::assertSame(0, $code);
        self::assertSame('', $out);
        self::assertStringStartsWith('<!doctype html>', (string) file_get_contents($file));
    }

    public function testAnalyzeAMissingProject(): void
    {
        [$code, , $err] = self::cli(['analyze', '/no/such/project']);
        self::assertSame(1, $code);
        self::assertStringContainsString('Project directory not found', $err);
    }

    /**
     * @param list<string> $args
     * @return array{int, string, string} exit code, standard output, standard error
     */
    private static function rulesFile(string $rules): string
    {
        $file = tempnam(sys_get_temp_dir(), 'untangled-rules');
        file_put_contents($file, $rules);
        register_shutdown_function(static fn () => @unlink($file));
        return $file;
    }

    private static function cli(array $args): array
    {
        $out = fopen('php://memory', 'w+');
        $err = fopen('php://memory', 'w+');
        $code = (new Application($out, $err))->run($args);
        rewind($out);
        rewind($err);
        return [$code, (string) stream_get_contents($out), (string) stream_get_contents($err)];
    }
}
