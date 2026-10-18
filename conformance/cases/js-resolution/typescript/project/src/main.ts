// SPDX-License-Identifier: MIT

// NodeNext: a .js specifier names the .ts file it is compiled from.
import { format } from "./util/format.js";
// No extension: .ts is tried before .js, so both.ts wins over both.js.
import { both } from "./both";
// A folder: its index file.
import { helpers } from "./util";
// A .jsx specifier names a .tsx file; .mjs names .mts and .cjs names .cts.
import { Button } from "./components/button.jsx";
import { esm } from "./legacy/esm.mjs";
import { cjs } from "./legacy/common.cjs";
// A file that exists as written, JavaScript included.
import { old } from "./legacy/old.js";
// JSON: an internal node that is not scanned.
import settings from "../settings.json";
// A query is dropped first.
import raw from "./util/format.js?raw";
// A declaration file: scanned because it is imported.
import type { Shape } from "./types/shapes";
// Missing: unresolved, as a path relative to the project root.
import { gone } from "./missing.js";
import { alsoGone } from "../src/missing.js";
// Leaving the project, or absolute: unresolved as written.
import { outside } from "../../outside.js";
import { absolute } from "/abs/path.js";

export const all = [format, both, helpers, Button, esm, cjs, old, settings, raw, gone, alsoGone, outside, absolute];
export type { Shape };
