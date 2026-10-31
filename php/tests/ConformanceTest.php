<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Untangled\Analysis\Analyzer;
use Untangled\Analysis\Clustering;
use Untangled\Analysis\Filter;
use Untangled\Cli\Application;
use Untangled\Diagnostic;
use Untangled\Graph\PairsDocument;
use Untangled\Report\Dot;
use Untangled\Report\Report;
use Untangled\Scanner\ClassAliases;
use Untangled\Scanner\ScanResult;
use Untangled\Scanner\Scanner;

/**
 * Runs the shared cases in conformance/cases (see conformance/README.md): every case with a
 * php/ folder, scanned with the --source paths in its php/sources file and the --aliases in its
 * php/aliases file if it has them, must produce its expected pairs, every expected analysis[.<strategy>].json, and
 * every expected graph[.<strategy>].dot byte for byte.
 */
final class ConformanceTest extends TestCase
{
    private const CASES = __DIR__ . '/../../conformance/cases';

    /** @return iterable<string, array{string}> */
    public static function cases(): iterable
    {
        foreach (glob(self::CASES . '/*/php', GLOB_ONLYDIR) ?: [] as $case) {
            yield basename(dirname($case)) => [$case];
        }
    }

    /** @return iterable<string, array{string, string}> */
    public static function analyses(): iterable
    {
        foreach (self::cases() as $name => [$case]) {
            foreach (glob($case . '/expected/analysis*.json') ?: [] as $file) {
                yield $name . ' ' . basename($file) => [$case, $file];
            }
        }
    }

    /** @return iterable<string, array{string, string}> */
    public static function graphs(): iterable
    {
        foreach (self::cases() as $name => [$case]) {
            foreach (glob($case . '/expected/graph*.dot') ?: [] as $file) {
                yield $name . ' ' . basename($file) => [$case, $file];
            }
        }
    }

    /** @return iterable<string, array{string, string}> */
    public static function diagnostics(): iterable
    {
        foreach (self::cases() as $name => [$case]) {
            if (is_file($case . '/expected/diagnostics.jsonl')) {
                yield $name => [$case, $case . '/expected/diagnostics.jsonl'];
            }
        }
    }

    /** @return iterable<string, array{string, string}> */
    public static function dependents(): iterable
    {
        foreach (self::cases() as $name => [$case]) {
            foreach (glob($case . '/expected/dependents.*') ?: [] as $file) {
                yield $name . ' ' . basename($file) => [$case, $file];
            }
        }
    }

    public function testThereAreCases(): void
    {
        self::assertGreaterThanOrEqual(8, iterator_count(self::cases()));
    }

    #[DataProvider('cases')]
    public function testPairs(string $case): void
    {
        $actual = self::scan($case)->pairs->toArray();
        self::assertSameDocument(self::read($case . '/expected/pairs.json'), $actual);
    }

    #[DataProvider('cases')]
    public function testEveryCaseHasAnExpectedAnalysis(string $case): void
    {
        self::assertFileExists($case . '/expected/analysis.json');
    }

    #[DataProvider('cases')]
    public function testScanIsDeterministic(string $case): void
    {
        $first = self::scan($case)->pairs->toJson();
        self::assertSame($first, self::scan($case)->pairs->toJson());
    }

    #[DataProvider('cases')]
    public function testExpectedPairsReadBackUnchanged(string $case): void
    {
        $expected = self::read($case . '/expected/pairs.json');
        self::assertSameDocument($expected, PairsDocument::fromArray($expected)->toArray());
    }

    #[DataProvider('analyses')]
    public function testAnalysis(string $case, string $file): void
    {
        $clustering = self::clustering($case, substr(basename($file, '.json'), strlen('analysis')));
        $pairs = self::scan($case)->pairs;
        $actual = (new Analyzer())->analyze((new Filter())->apply($pairs), $clustering);
        self::assertSameDocument(self::read($file), $actual);
    }

    /**
     * Runs `dependents` on the case's expected pairs document with the arguments, one per line, of
     * `dependents.<name>.args`. A .json expectation is compared as a document, a .txt one byte for byte.
     */
    #[DataProvider('dependents')]
    public function testDependents(string $case, string $file): void
    {
        $name = pathinfo($file, PATHINFO_FILENAME);
        $stdout = fopen('php://memory', 'w+');
        $stderr = fopen('php://memory', 'w+');
        $code = (new Application($stdout, $stderr))->run(['dependents', $case . '/expected/pairs.json', ...self::lines($case . '/' . $name . '.args')]);
        rewind($stdout);
        rewind($stderr);
        self::assertSame(0, $code, (string) stream_get_contents($stderr));
        $actual = (string) stream_get_contents($stdout);
        if (str_ends_with($file, '.json')) {
            self::assertSameDocument(self::read($file), json_decode($actual, true, 512, JSON_THROW_ON_ERROR));
            self::assertStringEndsWith("}\n", $actual);
        } else {
            self::assertSame(file_get_contents($file), $actual);
        }
    }

    #[DataProvider('graphs')]
    public function testDotGraph(string $case, string $file): void
    {
        $clustering = self::clustering($case, substr(basename($file, '.dot'), strlen('graph')));
        $pairs = self::scan($case)->pairs;
        $actual = Dot::render(Report::build(basename(dirname($case)), (new Filter())->apply($pairs), $clustering));
        self::assertSame(file_get_contents($file), $actual);
    }

    /**
     * The scan's diagnostics, one JSON object per line of `expected/diagnostics.jsonl`, are compared
     * on level, code and files, in order: the message is for people and is not pinned.
     */
    #[DataProvider('diagnostics')]
    public function testDiagnostics(string $case, string $file): void
    {
        $project = static fn (array $diagnostic): array => [$diagnostic['level'], $diagnostic['code'], $diagnostic['files'] ?? []];
        $expected = array_map(
            static fn (string $line): array => $project(json_decode($line, true, 512, JSON_THROW_ON_ERROR)),
            self::lines($file),
        );
        $actual = array_map(static fn (Diagnostic $diagnostic): array => $project($diagnostic->toArray()), self::scan($case)->diagnostics);
        self::assertSame($expected, $actual);
    }

    /**
     * Scans a case's project, with the --source paths listed one per line in its optional `sources`
     * file and the --aliases presets or files (relative to the case) in its optional `aliases` file.
     */
    private static function scan(string $case): ScanResult
    {
        $aliases = array_map(
            static fn (string $spec): string => is_file($case . '/' . $spec) ? $case . '/' . $spec : $spec,
            self::lines($case . '/aliases'),
        );
        return (new Scanner(sources: self::lines($case . '/sources'), aliases: ClassAliases::load($aliases)))->scan($case . '/project');
    }

    /** @return list<string> */
    private static function lines(string $file): array
    {
        return is_file($file) ? (file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: []) : [];
    }

    /** The clustering an expected file's suffix names: '' (none), '.rules', or '.namespace-2' and the like. */
    private static function clustering(string $case, string $suffix): ?Clustering
    {
        return match (true) {
            $suffix === '' => null,
            $suffix === '.rules' => Clustering::parseRules((string) file_get_contents($case . '/clusters.rules')),
            default => Clustering::fromString((string) preg_replace('/-(?=[0-9]+$)/', ':', substr($suffix, 1))),
        };
    }

    /**
     * Equality as the spec defines it for conformance: the generator is ignored and numbers
     * compare to 4 decimal places. Key order matters, as it does in the written documents.
     *
     * @param array<string, mixed> $expected
     * @param array<string, mixed> $actual
     */
    public static function assertSameDocument(array $expected, array $actual): void
    {
        unset($expected['generator'], $actual['generator']);
        self::assertSame(self::normalize($expected), self::normalize($actual));
    }

    private static function normalize(mixed $value): mixed
    {
        if (is_int($value) || is_float($value)) {
            return round((float) $value, 4);
        }
        return is_array($value) ? array_map(self::normalize(...), $value) : $value;
    }

    /** @return array<string, mixed> */
    public static function read(string $file): array
    {
        return json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
    }
}
