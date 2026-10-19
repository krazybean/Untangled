// SPDX-License-Identifier: MIT

// "." is the folder itself, here ./index.ts, a self-edge that is dropped; ".." is src/index.js.
import "." ;
import { root } from "..";

export const helpers = [root];
