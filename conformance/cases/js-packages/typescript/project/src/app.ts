// SPDX-License-Identifier: MIT

// Declared in package.json, in any of the four dependency fields.
import React from "react";
import { Button } from "@scope/ui/button";
import { test } from "vitest";
import map from "lodash/map";
import "fsevents";
// Not declared, but installed in node_modules.
import { thing } from "installed-only";
// Neither: unresolved, as written.
import pad from "left-pad";
import { deep } from "@nobody/pkg/deep";
// Declared and installed only for tools/, not for this file.
import { Command } from "commander";
import chalk from "chalk";
// Builtins, with or without node:. A declared package wins over a builtin of the same name.
import { readFile } from "node:fs/promises";
import { join } from "path";
import { EventEmitter } from "events";
import { Buffer } from "buffer";
import test2 from "node:test";
// Package imports from package.json's "imports".
import { slug } from "#utils/slug";
import config from "#config";
import { format } from "#date";
import { gone } from "#gone";
import { nothing } from "#nothing";

export const all = [React, Button, test, map, thing, pad, deep, Command, chalk, readFile, join, EventEmitter, Buffer, test2, slug, config, format, gone, nothing];
