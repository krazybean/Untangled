<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Composer;

use PHPUnit\Framework\TestCase;
use Untangled\Composer\ComposerProject;
use Untangled\Composer\ProjectException;
use Untangled\Tests\TempProject;

final class ComposerProjectTest extends TestCase
{
    private ?TempProject $project = null;

    protected function tearDown(): void
    {
        $this->project?->remove();
    }

    public function testAMissingDirectoryIsAnError(): void
    {
        $this->expectException(ProjectException::class);
        $this->expectExceptionMessage('Project directory not found: /no/such/dir');
        ComposerProject::load('/no/such/dir');
    }

    public function testAFileIsNotAProject(): void
    {
        $this->expectException(ProjectException::class);
        ComposerProject::load(__FILE__);
    }

    public function testADirectoryWithoutComposerJsonIsAnError(): void
    {
        $this->project = new TempProject(['index.php' => '<?php']);
        $this->expectException(ProjectException::class);
        $this->expectExceptionMessage('No composer.json');
        ComposerProject::load($this->project->root);
    }

    public function testInvalidJsonIsAnError(): void
    {
        $this->project = new TempProject(['composer.json' => '{"autoload": ']);
        $this->expectException(ProjectException::class);
        $this->expectExceptionMessage('composer.json is not valid JSON');
        ComposerProject::load($this->project->root);
    }

    public function testComposerJsonMustBeAnObject(): void
    {
        $this->project = new TempProject(['composer.json' => '"just a string"']);
        $this->expectException(ProjectException::class);
        $this->expectExceptionMessage('must contain a JSON object');
        ComposerProject::load($this->project->root);
    }

    public function testTheRootIsAbsoluteAndNormalized(): void
    {
        $this->project = new TempProject(['composer.json' => [], 'sub/x.txt' => '']);
        $project = ComposerProject::load($this->project->root . '/sub/..');
        self::assertSame($this->project->root, $project->root);
    }

    public function testVendorDir(): void
    {
        $this->project = new TempProject(['composer.json' => []]);
        self::assertSame('vendor', ComposerProject::load($this->project->root)->vendorDir());
        $this->project->write('composer.json', ['config' => ['vendor-dir' => './lib/deps/']]);
        self::assertSame('lib/deps', ComposerProject::load($this->project->root)->vendorDir());
        $this->project->write('composer.json', ['config' => ['vendor-dir' => 42]]);
        self::assertSame('vendor', ComposerProject::load($this->project->root)->vendorDir());
    }

    public function testPackagesFromInstalledJsonWinOverTheLockfile(): void
    {
        $this->project = new TempProject([
            'composer.json' => [],
            'composer.lock' => ['packages' => [['name' => 'from/lock']]],
            'vendor/composer/installed.json' => ['packages' => [['name' => 'z/last', 'install-path' => '../z/last'], ['name' => 'a/first']]],
        ]);
        $packages = ComposerProject::load($this->project->root)->packages();
        self::assertSame(['a/first', 'z/last'], array_map(static fn ($p) => $p->name, $packages));
        self::assertSame($this->project->root . '/vendor/a/first', $packages[0]->installPath);
        self::assertSame($this->project->root . '/vendor/z/last', $packages[1]->installPath);
    }

    public function testComposerOneInstalledJsonIsAList(): void
    {
        $this->project = new TempProject(['composer.json' => [], 'vendor/composer/installed.json' => [['name' => 'old/style']]]);
        self::assertSame('old/style', ComposerProject::load($this->project->root)->packages()[0]->name);
    }

    public function testLockfilePackagesIncludeDevAndHaveNoInstallPath(): void
    {
        $this->project = new TempProject([
            'composer.json' => [],
            'composer.lock' => ['packages' => [['name' => 'b/run']], 'packages-dev' => [['name' => 'a/dev'], ['no' => 'name']]],
        ]);
        $packages = ComposerProject::load($this->project->root)->packages();
        self::assertSame(['a/dev', 'b/run'], array_map(static fn ($p) => $p->name, $packages));
        self::assertNull($packages[0]->installPath);
    }

    public function testNoVendorAndNoLockfileMeansNoPackages(): void
    {
        $this->project = new TempProject(['composer.json' => []]);
        self::assertSame([], ComposerProject::load($this->project->root)->packages());
    }

    public function testACorruptLockfileMeansNoPackages(): void
    {
        $this->project = new TempProject(['composer.json' => [], 'composer.lock' => '{nope']);
        self::assertSame([], ComposerProject::load($this->project->root)->packages());
    }
}
