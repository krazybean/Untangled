#!/usr/bin/env node
// SPDX-License-Identifier: MIT
import { main } from "../dist/cli.js";

process.exitCode = main(process.argv.slice(2));
