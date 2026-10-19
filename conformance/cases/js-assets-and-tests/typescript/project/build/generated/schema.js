// SPDX-License-Identifier: MIT

// Build output, but added back with --source (typescript/sources), so it is scanned.
import { request } from "../../src/http.js";

export const generated = request;
