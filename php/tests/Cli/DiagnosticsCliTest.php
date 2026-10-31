<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Cli;

use PHPUnit\Framework\TestCase;
use Untangled\Cli\Application;
use Untangled\Tests\TempProject;

/** `--diagnostics=json` (spec/diagnostics.md): JSON Lines on standard error, nothing else changes. */
final class DiagnosticsCliTest extends TestCase
{
    private const LAYERS = __DIR__ . '/../../../conformance/cases/layers/php';

    private ?TempProject $project = null;

    protected function tearDown(): void
    {
        $this->project?->remove();
    }

    /** @param list<string> $args @return array{int, string, string} */
    private static function cli(array $args): array
    {
        $out = fopen('php://memory', 'w+');
        $err = fopen('php://memory', 'w+');
        $code = (new Application($out, $err))->run($args);
        rewind($out);
        rewind($err);
        return [$code, (string) stream_get_contents($out), (string) stream_get_contents($err)];
    }

    /** @return list<array<string, mixed>> the diagnostics on standard error, each line parsed */
    private static function lines(string $err): array
    {
        $lines = [];
        foreach (explode("\n", rtrim($err, "\n")) as $line) {
            $lines[] = json_decode($line, true, 512, JSON_THROW_ON_ERROR);
        }
        return $lines;
    }

    private function messyProject(): string
    {
        $this->project = new TempProject([
            'composer.json' => ['autoload' => ['psr-4' => ['App\\' => 'src/']]],
            'src/A.php' => '<?php namespace App; class A {}',
            'src/Broken.php' => '<?php class {',
            'scripts/x.php' => '<?php',
        ]);
        return $this->project->root;
    }

    public function testTextIsTheDefaultAndJsonSaysTheSameThing(): void
    {
        $root = $this->messyProject();
        [$code, $out, $text] = self::cli(['scan', $root]);
        [$jsonCode, $jsonOut, $json] = self::cli(['scan', $root, '--diagnostics=json']);
        [, , $explicit] = self::cli(['scan', $root, '--diagnostics=text']);
        self::assertSame([0, 0], [$code, $jsonCode]);
        self::assertSame($out, $jsonOut, 'standard output is the same in both modes');
        self::assertSame($text, $explicit);
        $textLines = explode("\n", rtrim($text, "\n"));
        $lines = self::lines($json);
        self::assertCount(2, $lines);
        foreach ($lines as $index => $line) {
            self::assertSame("{$line['level']}: {$line['message']}", $textLines[$index]);
        }
        self::assertSame([['warning', 'file-unparseable', ['src/Broken.php']], ['warning', 'uncovered-files', ['scripts/x.php']]], array_map(
            static fn (array $line): array => [$line['level'], $line['code'], $line['files']],
            $lines,
        ));
        self::assertStringStartsWith('warning: src/Broken.php: parse error', $textLines[0]);
    }

    public function testTheLinesAreTheSameEveryTime(): void
    {
        $root = $this->messyProject();
        self::assertSame(self::cli(['scan', $root, '--diagnostics=json']), self::cli(['scan', $root, '--diagnostics=json']));
    }

    public function testNoDiagnosticsMeansNothingOnStandardError(): void
    {
        $layers = self::LAYERS . '/project';
        foreach (['text', 'json'] as $format) {
            [$code, $out, $err] = self::cli(['scan', $layers, "--diagnostics={$format}"]);
            self::assertSame(0, $code);
            self::assertNotSame('', $out);
            self::assertSame('', $err);
        }
    }

    public function testEveryCommandTakesTheOption(): void
    {
        $pairs = self::LAYERS . '/expected/pairs.json';
        foreach ([['scan', self::LAYERS . '/project'], ['analyze', $pairs], ['report', $pairs], ['dependents', $pairs, 'src/Domain/User.php']] as $args) {
            [$code, $out, $err] = self::cli([...$args, '--diagnostics=json']);
            self::assertSame(0, $code, implode(' ', $args));
            self::assertNotSame('', $out);
            self::assertSame('', $err);
        }
    }

    public function testAnUnknownFormatIsAUsageError(): void
    {
        foreach (['github', 'xml', ''] as $format) {
            [$code, $out, $err] = self::cli(['scan', self::LAYERS . '/project', "--diagnostics={$format}"]);
            self::assertSame(2, $code);
            self::assertSame('', $out);
            self::assertSame("Unknown diagnostics format: {$format} (use text or json)\n", $err);
        }
        [$code, , $err] = self::cli(['scan', self::LAYERS . '/project', '--diagnostics']);
        self::assertSame(2, $code);
        self::assertStringContainsString('Option --diagnostics needs a value', $err);
    }

    public function testUsageErrorsStayTextInJsonMode(): void
    {
        [$code, , $err] = self::cli(['scan', '.', '--nope', '--diagnostics=json']);
        self::assertSame(2, $code);
        self::assertSame("Unknown option for scan: --nope\n", $err);
    }

    public function testUnmatchedRulesAreAWarningOrWithStrictAnError(): void
    {
        $pairs = self::LAYERS . '/expected/pairs.json';
        $rules = tempnam(sys_get_temp_dir(), 'untangled-rules');
        file_put_contents($rules, "src/Domain/ Core\n");
        try {
            [$code, $out, $err] = self::cli(['analyze', $pairs, "--cluster=rules:{$rules}", '--diagnostics=json']);
            self::assertSame(0, $code);
            self::assertNotSame('', $out);
            $line = self::lines($err)[0];
            self::assertSame(['warning', 'unmatched-rules'], [$line['level'], $line['code']]);
            self::assertSame(
                ['bootstrap.php', 'src/Http/Router.php', 'src/Http/UserController.php', 'src/Infra/Clock.php', 'src/Infra/UserRepository.php'],
                $line['files'],
            );
            self::assertStringStartsWith('warning: ' . $line['message'], self::cli(['analyze', $pairs, "--cluster=rules:{$rules}"])[2]);

            [$code, $out, $err] = self::cli(['analyze', $pairs, "--cluster=rules:{$rules}", '--strict', '--diagnostics=json']);
            self::assertSame([1, ''], [$code, $out]);
            self::assertCount(1, self::lines($err));
            self::assertSame(['error', 'unmatched-rules', $line['files']], [self::lines($err)[0]['level'], self::lines($err)[0]['code'], self::lines($err)[0]['files']]);
            self::assertSame('error: ' . $line['message'] . "\n", self::cli(['analyze', $pairs, "--cluster=rules:{$rules}", '--strict'])[2]);
        } finally {
            unlink($rules);
        }
    }

    public function testThePairsDocumentVersionIsADiagnostic(): void
    {
        $file = tempnam(sys_get_temp_dir(), 'untangled-pairs');
        $data = json_decode((string) file_get_contents(self::LAYERS . '/expected/pairs.json'), true);
        $data['version'] = '0.99';
        file_put_contents($file, json_encode($data));
        try {
            [$code, , $err] = self::cli(['analyze', $file, '--diagnostics=json']);
            self::assertSame(0, $code);
            self::assertSame(['warning', 'document-version'], [self::lines($err)[0]['level'], self::lines($err)[0]['code']]);
        } finally {
            unlink($file);
        }
    }

    /** @return iterable<string, array{list<string>, int, string}> */
    public static function failures(): iterable
    {
        $pairs = self::LAYERS . '/expected/pairs.json';
        yield 'project' => [['scan', '/no/such/folder'], 1, 'project-unreadable'];
        yield 'project, for analyze' => [['analyze', '/no/such/folder'], 1, 'project-unreadable'];
        yield 'rules file' => [['analyze', $pairs, '--cluster=rules:/no/such/rules'], 1, 'rules-file-unreadable'];
        yield 'aliases' => [['scan', self::LAYERS . '/project', '--aliases=/no/such/aliases.json'], 1, 'aliases-unusable'];
        yield 'target' => [['dependents', $pairs, 'src/Nope.php'], 1, 'target-not-found'];
        yield 'target outside' => [['dependents', self::LAYERS . '/project', '/no/such/src/Domain/User.php'], 1, 'target-outside-project'];
    }

    /** @param list<string> $args */
    #[\PHPUnit\Framework\Attributes\DataProvider('failures')]
    public function testAFailureIsTheLastDiagnosticAndAnError(array $args, int $exit, string $code): void
    {
        [$exitCode, $out, $err] = self::cli([...$args, '--diagnostics=json']);
        self::assertSame([$exit, ''], [$exitCode, $out]);
        $lines = self::lines($err);
        $last = $lines[count($lines) - 1];
        self::assertSame(['error', $code], [$last['level'], $last['code']]);
        // Text mode says the same, as before.
        [$textCode, , $text] = self::cli($args);
        self::assertSame($exit, $textCode);
        self::assertSame('error: ' . $last['message'] . "\n", $text);
    }

    public function testDocumentsThatCannotBeUsed(): void
    {
        $this->project = new TempProject(['bad.json' => '{nope', 'list.json' => '[]', 'clustered.json' => json_encode([
            'format' => 'untangled-pairs', 'version' => '0.1', 'language' => 'php', 'nodes' => [['id' => 'a', 'kind' => 'cluster']], 'edges' => [],
        ])]);
        $root = $this->project->root;
        foreach (['bad.json', 'list.json'] as $file) {
            [$code, , $err] = self::cli(['analyze', "{$root}/{$file}", '--diagnostics=json']);
            self::assertSame(1, $code);
            self::assertSame(['error', 'document-invalid'], [self::lines($err)[0]['level'], self::lines($err)[0]['code']]);
        }
        [$code, , $err] = self::cli(['analyze', "{$root}/clustered.json", '--diagnostics=json']);
        self::assertSame(1, $code);
        self::assertSame('document-clustered', self::lines($err)[0]['code']);
        [$code, , $err] = self::cli(['dependents', "{$root}/clustered.json", 'a', '--diagnostics=json']);
        self::assertSame(1, $code);
        self::assertSame('document-clustered', self::lines($err)[0]['code']);
    }

    public function testAnOutputThatCannotBeWritten(): void
    {
        [$code, $out, $err] = self::cli(['scan', self::LAYERS . '/project', '--output=/no/such/folder/pairs.json', '--diagnostics=json']);
        self::assertSame([1, ''], [$code, $out]);
        self::assertSame(['error', 'output-unwritable'], [self::lines($err)[0]['level'], self::lines($err)[0]['code']]);
    }
}
