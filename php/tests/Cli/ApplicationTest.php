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
