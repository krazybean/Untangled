// SPDX-License-Identifier: MIT

// A syntax error the parser recovers from: the imports are still read.
import { value } from "./a";
let twice = 1;
let twice = 2;
export { value, twice };
