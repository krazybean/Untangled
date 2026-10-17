<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Report;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Untangled\Analysis\Clustering;
use Untangled\Analysis\Filter;
use Untangled\Graph\PairsDocument;
use Untangled\Report\Dot;
use Untangled\Report\HtmlReport;
use Untangled\Report\Report;
use Untangled\Scanner\Scanner;
use Untangled\Tests\Graph\PairsBuilder;

/** The HTML report of spec/report.md. */
final class HtmlReportTest extends TestCase
{
    private const CASES = __DIR__ . '/../../../conformance/cases';

    private static function demo(): string
    {
        return HtmlReport::render(Report::build('Demo <app>', ReportTest::demo()), new \DateTimeImmutable('2026-10-17'));
    }

    public function testIsOneSelfContainedPage(): void
    {
        $html = self::demo();
        self::assertStringStartsWith('<!doctype html>', $html);
        self::assertDoesNotMatchRegularExpression('/<(?:script|link|img)[^>]+(?:src|href)=["\']?(?:https?:)?\/\//i', $html);
        self::assertDoesNotMatchRegularExpression('/<(?:script|link)[^>]+(?:src|href)=/i', $html);
        self::assertStringNotContainsString('@import', $html);
    }

    public function testEscapesNamesInMarkupAndData(): void
    {
        $html = self::demo();
        self::assertStringContainsString('<h1>Demo &lt;app&gt;</h1>', $html);
        self::assertStringNotContainsString('</script><b>', $html);
        // The two closing tags are the inline script and the embedded data, nothing injected.
        self::assertSame(2, substr_count($html, '</script>'));
    }

    public function testSectionsComeInTheSpecifiedOrder(): void
    {
        $html = HtmlReport::render(self::grouped());
        $positions = array_map(static fn (string $id): int|false => strpos($html, "<section id=\"{$id}\""), ['summary', 'why', 'map', 'cycles', 'hotspots', 'parts', 'outside', 'groups', 'glossary']);
        self::assertNotContains(false, $positions);
        $sorted = $positions;
        sort($sorted);
        self::assertSame($sorted, $positions);
    }

    public function testStatesTheCycles(): void
    {
        $html = self::demo();
        self::assertStringContainsString('1 dependency cycle found.', $html);
        self::assertStringContainsString('2 parts of 3 (67%) are caught in a loop', $html);
    }

    public function testSaysWhenThereAreNoCycles(): void
    {
        $html = HtmlReport::render(self::scanned('psr4-basic'));
        self::assertStringContainsString('No dependency cycles.', $html);
        self::assertStringNotContainsString('id="groups"', $html);
    }

    /** @return iterable<string, array{string}> */
    public static function fileLevelLines(): iterable
    {
        foreach (HtmlReport::PLAIN as $key => $sentence) {
            if (!in_array($key, ['ca', 'ce'], true)) {
                yield $key => [$sentence];
            }
        }
    }

    #[DataProvider('fileLevelLines')]
    public function testUsesThePlainLanguageLinesVerbatim(string $sentence): void
    {
        self::assertStringContainsString(htmlspecialchars($sentence, ENT_QUOTES), self::demo());
    }

    public function testPlainLanguageLinesMatchTheSpec(): void
    {
        // The spec wraps long lines, so compare with runs of whitespace collapsed.
        $spec = (string) preg_replace('/\s+/', ' ', (string) file_get_contents(__DIR__ . '/../../../spec/metrics.md'));
        foreach (['fan_out', 'fan_in', 'external', 'unresolved', 'instability', 'cycle'] as $key) {
            self::assertStringContainsString(HtmlReport::PLAIN[$key], $spec, "spec/metrics.md must contain the {$key} line");
        }
    }

    public function testShowsTheGenerationDate(): void
    {
        self::assertStringContainsString('Generated 17 October 2026', self::demo());
    }

    public function testEmbedsTheGraphAndTheDotFile(): void
    {
        $report = Report::build('Demo', ReportTest::demo());
        preg_match('#<script type="application/json" id="untangled-data">(.*?)</script>#s', HtmlReport::render($report), $match);
        $data = json_decode($match[1] ?? '', true);
        self::assertIsArray($data);
        self::assertCount(3, $data['units']);
        self::assertSame(1, $data['units'][0]['cycle']);
        self::assertNull($data['units'][2]['cycle']);
        self::assertSame(Dot::render($report), $data['dot']);
        self::assertFalse($data['clustered']);
    }

    public function testClusteredReportsExplainTheGrouping(): void
    {
        $html = HtmlReport::render(self::grouped());
        self::assertStringContainsString('share the first 2 levels of their namespace', $html);
        self::assertStringContainsString('id="groups"', $html);
        self::assertStringContainsString(htmlspecialchars(HtmlReport::PLAIN['ca']), $html);
        self::assertStringContainsString(htmlspecialchars(HtmlReport::PLAIN['ce']), $html);
    }

    public function testDescribesEachGrouping(): void
    {
        $doc = PairsBuilder::build(['a/1.php -> b/1.php']);
        self::assertStringContainsString('Each part is one file.', HtmlReport::render(Report::build('x', $doc)));
        self::assertStringContainsString('share the first 1 level of their folder path', HtmlReport::render(Report::build('x', $doc, Clustering::fromString('folder:1'))));
        self::assertStringContainsString('as set by a rules file', HtmlReport::render(Report::build('x', $doc, Clustering::parseRules('a/ A'))));
    }

    public function testAnEmptyProjectStillRenders(): void
    {
        self::assertStringContainsString('nothing to report yet', HtmlReport::render(Report::build('Empty', new PairsDocument('php'))));
    }

    public function testNullInstabilityIsShownAsNone(): void
    {
        self::assertSame('none', HtmlReport::instability(null));
        self::assertSame('0.00', HtmlReport::instability(0));
        self::assertSame('0.33', HtmlReport::instability(0.3333));
        self::assertSame('1.00', HtmlReport::instability(1));
    }

    public function testCount(): void
    {
        self::assertSame('1 file', HtmlReport::count(1, 'file'));
        self::assertSame('0 files', HtmlReport::count(0, 'file'));
        self::assertSame('2 dependencies', HtmlReport::count(2, 'dependency', 'dependencies'));
    }

    public function testUnresolvedName(): void
    {
        self::assertSame('App\\Gone (class)', HtmlReport::unresolvedName('unresolved:class:App\\Gone'));
        self::assertSame("\$a . 'x.php' (include)", HtmlReport::unresolvedName("unresolved:include:\$a . 'x.php'"));
        self::assertSame('weird', HtmlReport::unresolvedName('weird'));
    }

    public function testListsPackagesAndUnresolvedReferences(): void
    {
        $html = HtmlReport::render(self::scanned('composer-packages'));
        foreach (['composer:monolog/monolog', 'composer:psr/log', 'composer:acme/legacy-pdf'] as $package) {
            self::assertStringContainsString(substr($package, strlen('composer:')), $html);
        }
        self::assertStringContainsString('App\\Models\\User', $html);
    }

    private static function scanned(string $case, ?Clustering $clustering = null): Report
    {
        $pairs = (new Scanner())->scan(self::CASES . "/{$case}/php/project")->pairs;
        return Report::build($case, (new Filter())->apply($pairs), $clustering);
    }

    private static function grouped(): Report
    {
        return self::scanned('layers', Clustering::fromString('namespace:2'));
    }
}
