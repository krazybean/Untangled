// SPDX-License-Identifier: MIT

// tools/ has its own package.json: its dependencies and imports, plus the root ones.
import { Command } from "commander";
import chalk from "chalk";
import React from "react";
import { help } from "#helpers";
import config from "#config";

export const all = [Command, chalk, React, help, config];
