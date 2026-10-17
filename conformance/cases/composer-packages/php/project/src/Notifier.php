<?php
// SPDX-License-Identifier: MIT

namespace App;

use Monolog\Logger;
use Monolog\Handler\StreamHandler;
use Psr\Log\LoggerInterface;
use App\Models;

final class Notifier
{
    public function __construct(private LoggerInterface $logger)
    {
    }

    public static function create(): self
    {
        $logger = new Logger('app');
        $logger->pushHandler(new StreamHandler('php://stderr'));
        return new self($logger);
    }

    public function attach(): \Acme_Pdf_Document
    {
        return new \Acme_Pdf_Document(Models\User::class);
    }
}
