<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Scanner;

use PHPUnit\Framework\TestCase;
use Untangled\Diagnostic;
use Untangled\Graph\PairsDocument;
use Untangled\Scanner\FileResult;
use Untangled\Scanner\FileScanner;
use Untangled\Scanner\ScanResult;
use Untangled\Scanner\Scanner;
use Untangled\Tests\TempProject;

/** The structured diagnostics of a scan (spec/diagnostics.md): codes, levels and files, not messages. */
final class ScannerDiagnosticsTest extends TestCase
{
    private ?TempProject $project = null;

    protected function tearDown(): void
    {
        $this->project?->remove();
    }

    /**
     * @param array<string, string> $files
     * @param array<string, mixed> $composer
     * @param list<string> $sources
     * @return list<array{string, string, list<string>}> level, code and files of each diagnostic
     */
    private function scan(array $files, array $composer = ['autoload' => ['psr-4' => ['App\\' => 'src/']]], array $sources = []): array
    {
        $this->project = new TempProject(['composer.json' => $composer] + $files);
        $result = (new Scanner(sources: $sources))->scan($this->project->root);
        // The older warnings are the messages of the warning diagnostics, in order.
        self::assertSame(
            array_values(array_map(static fn (Diagnostic $d): string => $d->message, array_filter($result->diagnostics, static fn (Diagnostic $d): bool => $d->level === 'warning'))),
            $result->warnings,
        );
        return array_map(static fn (Diagnostic $d): array => [$d->level, $d->code, $d->files], $result->diagnostics);
    }

    public function testACleanScanHasNone(): void
    {
        self::assertSame([], $this->scan(['src/A.php' => '<?php namespace App; class A {}']));
    }

    public function testAFileThatDoesNotParse(): void
    {
        self::assertSame(
            [['warning', 'file-unparseable', ['src/Broken.php']]],
            $this->scan(['src/A.php' => '<?php namespace App;', 'src/Broken.php' => '<?php class {']),
        );
    }

    public function testASourceThatDoesNotExist(): void
    {
        self::assertSame(
            [['warning', 'source-not-found', ['nope/deeper']]],
            $this->scan(['src/A.php' => '<?php namespace App;'], sources: ['./nope/deeper/']),
        );
    }

    public function testNothingToScan(): void
    {
        self::assertSame([['warning', 'nothing-scanned', []]], $this->scan([], ['name' => 'x/y']));
    }

    public function testUncoveredFilesAreOneDiagnosticListingThemAll(): void
    {
        self::assertSame(
            [['warning', 'uncovered-files', ['routes/api.php', 'routes/web.php', 'scripts/x.php']]],
            $this->scan([
                'src/A.php' => '<?php namespace App;',
                'scripts/x.php' => '<?php',
                'routes/web.php' => '<?php',
                'routes/api.php' => '<?php',
            ]),
        );
    }

    public function testAClassDeclaredInTwoFiles(): void
    {
        self::assertSame(
            [['warning', 'duplicate-declaration', ['src/B.php', 'src/A.php']]],
            $this->scan(['src/A.php' => '<?php namespace App; class Dup {}', 'src/B.php' => '<?php namespace App; class Dup {}']),
        );
    }

    public function testPackagesThatCannotBeListed(): void
    {
        $composer = ['require' => ['acme/x' => '^1.0'], 'autoload' => ['psr-4' => ['App\\' => 'src/']]];
        self::assertSame([['warning', 'package-list-missing', []]], $this->scan(['src/A.php' => '<?php namespace App;'], $composer));
        self::assertSame(
            [['warning', 'package-list-unreadable', []]],
            $this->scan(['src/A.php' => '<?php namespace App;', 'composer.lock' => '{nope'], $composer),
        );
    }

    public function testSeveralDiagnosticsKeepTheOrderOfTheScan(): void
    {
        self::assertSame(
            [
                ['warning', 'source-not-found', ['nope']],
                ['warning', 'file-unparseable', ['src/Broken.php']],
                ['warning', 'uncovered-files', ['scripts/x.php']],
            ],
            $this->scan(['src/Broken.php' => '<?php class {', 'scripts/x.php' => '<?php'], sources: ['nope']),
        );
    }

    public function testTheVersionOfAPairsDocument(): void
    {
        $warnings = [];
        $diagnostics = [];
        PairsDocument::fromArray(['format' => 'untangled-pairs', 'version' => '0.99', 'language' => 'php', 'nodes' => [], 'edges' => []], $warnings, $diagnostics);
        self::assertCount(1, $diagnostics);
        self::assertSame(['warning', 'document-version'], [$diagnostics[0]->level, $diagnostics[0]->code]);
        self::assertSame([$diagnostics[0]->message], $warnings);
    }

    public function testAFileThatCannotBeReadIsReportedAsUnreadable(): void
    {
        // A path that does not exist cannot be read on any platform, whatever the permissions or the user.
        $result = (new FileScanner())->scan(sys_get_temp_dir() . '/untangled-no-such-file-' . bin2hex(random_bytes(6)) . '.php');
        self::assertSame('read', $result->unread);
        self::assertNotNull($result->error);

        // The scanner turns a failed read into file-unreadable, and a failed parse into file-unparseable.
        $diagnostic = (new \ReflectionMethod(Scanner::class, 'fileDiagnostic'))->invoke(null, 'src/Locked.php', $result);
        self::assertSame(['warning', 'file-unreadable', ['src/Locked.php']], [$diagnostic->level, $diagnostic->code, $diagnostic->files]);
        self::assertSame("src/Locked.php: {$result->error}", $diagnostic->message);
        $parse = (new \ReflectionMethod(Scanner::class, 'fileDiagnostic'))->invoke(null, 'src/Bad.php', FileResult::failed('parse error: x', 'parse'));
        self::assertSame('file-unparseable', $parse->code);
    }
}
