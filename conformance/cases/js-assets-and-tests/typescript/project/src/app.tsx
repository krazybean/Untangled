// SPDX-License-Identifier: MIT

// Files that are not code give no edge (the scan warns with how many per extension).
import "./app.css";
import logo from "./logo.svg";
import icon from "./icon.svg?url";
// Build output imported by source: an internal node that is not scanned.
import { legacy } from "../dist/legacy.js";
// A test helper that real code imports: scanned, though tests are not scanned by default.
import { fakeApi } from "./__mocks__/api";
import { generated } from "../build/generated/schema.js";

export const App = () => <img src={logo} alt={icon} data-x={[legacy, fakeApi, generated].length} />;
