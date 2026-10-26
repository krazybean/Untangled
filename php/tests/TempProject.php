<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests;

use Untangled\Path;

/**
 * A throwaway project directory for tests that need files on disk. Paths are relative
 * to the project root; arrays are written as JSON.
 */
final class TempProject
{
    public readonly string $root;

    /** @param array<string, string|array<mixed>> $files */
    public function __construct(array $files)
    {
        $root = sys_get_temp_dir() . '/untangled-test-' . bin2hex(random_bytes(6));
        mkdir($root, 0777, true);
        $this->root = Path::normalize((string) realpath($root));
        foreach ($files as $path => $contents) {
            $this->write($path, $contents);
        }
    }

    /** @param string|array<mixed> $contents */
    public function write(string $path, string|array $contents): void
    {
        $file = $this->root . '/' . $path;
        if (!is_dir(dirname($file))) {
            mkdir(dirname($file), 0777, true);
        }
        file_put_contents($file, is_array($contents) ? json_encode($contents, JSON_UNESCAPED_SLASHES) : $contents);
    }

    public function remove(): void
    {
        $iterator = new \RecursiveIteratorIterator(
            new \RecursiveDirectoryIterator($this->root, \FilesystemIterator::SKIP_DOTS),
            \RecursiveIteratorIterator::CHILD_FIRST,
        );
        foreach ($iterator as $file) {
            /** @var \SplFileInfo $file */
            // git makes its object files read-only, which Windows will not delete.
            if ($file->isDir()) {
                rmdir($file->getPathname());
                continue;
            }
            chmod($file->getPathname(), 0666);
            unlink($file->getPathname());
        }
        rmdir($this->root);
    }
}
