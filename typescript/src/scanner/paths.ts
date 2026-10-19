// SPDX-License-Identifier: MIT
// Project-relative POSIX paths, the ids of internal nodes.

import { posix } from "node:path";

/**
 * Joins a project-relative folder ("" for the root) and a relative path. Returns undefined
 * when the result leaves the project.
 */
export function joinPath(folder: string, path: string): string | undefined {
  const joined = posix.normalize(folder ? `${folder}/${path}` : path);
  if (joined === ".." || joined.startsWith("../") || posix.isAbsolute(joined)) {
    return undefined;
  }
  const trimmed = joined.replace(/\/$/, "");
  return trimmed === "." ? "" : trimmed;
}

export function folderOf(id: string): string {
  const slash = id.lastIndexOf("/");
  return slash === -1 ? "" : id.slice(0, slash);
}

export function isUnder(id: string, folder: string): boolean {
  return folder === "" || id === folder || id.startsWith(folder + "/");
}
