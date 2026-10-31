// SPDX-License-Identifier: MIT
// Glob patterns on internal ids (spec/clustering.md): `*` and `?` stay within one path segment,
// `**` matches across `/`, and `**` followed by `/` also matches no folder at all.

export class Glob {
  private readonly regex: RegExp;

  constructor(readonly pattern: string) {
    let regex = "";
    // By code point, so `?` matches one character even outside the Basic Multilingual Plane.
    const chars = [...pattern];
    for (let index = 0; index < chars.length; index++) {
      const char = chars[index]!;
      if (char === "*" && chars[index + 1] === "*") {
        index++;
        if (chars[index + 1] === "/") {
          index++;
          regex += "(?:.*/)?";
        } else {
          regex += ".*";
        }
      } else if (char === "*") {
        regex += "[^/]*";
      } else if (char === "?") {
        regex += "[^/]";
      } else {
        regex += char.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
      }
    }
    this.regex = new RegExp(`^${regex}$`, "su");
  }

  matches(id: string): boolean {
    return this.regex.test(id);
  }
}
