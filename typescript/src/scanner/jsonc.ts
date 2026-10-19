// SPDX-License-Identifier: MIT
// JSON with comments and trailing commas, as tsconfig.json and jsconfig.json are written.

/** Parses JSON that may hold // and /* *\/ comments and trailing commas. Throws SyntaxError. */
export function parseJsonc(text: string): unknown {
  let out = "";
  let index = 0;
  while (index < text.length) {
    const char = text[index]!;
    if (char === '"') {
      const end = stringEnd(text, index);
      out += text.slice(index, end);
      index = end;
    } else if (char === "/" && text[index + 1] === "/") {
      while (index < text.length && text[index] !== "\n") {
        index++;
      }
    } else if (char === "/" && text[index + 1] === "*") {
      const end = text.indexOf("*/", index + 2);
      index = end === -1 ? text.length : end + 2;
      out += " ";
    } else {
      out += char;
      index++;
    }
  }
  return JSON.parse(withoutTrailingCommas(out));
}

function stringEnd(text: string, start: number): number {
  let index = start + 1;
  while (index < text.length && text[index] !== '"') {
    index += text[index] === "\\" ? 2 : 1;
  }
  return index + 1;
}

function withoutTrailingCommas(text: string): string {
  let out = "";
  let index = 0;
  while (index < text.length) {
    const char = text[index]!;
    if (char === '"') {
      const end = stringEnd(text, index);
      out += text.slice(index, end);
      index = end;
      continue;
    }
    if (char === ",") {
      let next = index + 1;
      while (next < text.length && /\s/.test(text[next]!)) {
        next++;
      }
      if (text[next] === "}" || text[next] === "]") {
        index++;
        continue;
      }
    }
    out += char;
    index++;
  }
  return out;
}
