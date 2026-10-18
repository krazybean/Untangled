// SPDX-License-Identifier: MIT
// Text helpers for names and paths read from source code and the filesystem.

const utf8Decoder = new TextDecoder("utf-8", { fatal: true, ignoreBOM: false });

// The characters Windows-1252 gives to bytes 0x80 to 0x9f; the five it leaves undefined
// are read as Latin-1, so nothing is replaced or rejected.
const WINDOWS_1252_HIGH = [
  0x20ac, 0x81, 0x201a, 0x0192, 0x201e, 0x2026, 0x2020, 0x2021, 0x02c6, 0x2030, 0x0160, 0x2039, 0x0152, 0x8d,
  0x017d, 0x8f, 0x90, 0x2018, 0x2019, 0x201c, 0x201d, 0x2022, 0x2013, 0x2014, 0x02dc, 0x2122, 0x0161, 0x203a,
  0x0153, 0x9d, 0x017e, 0x0178,
];

/**
 * Decodes UTF-8 (dropping a BOM), or else Windows-1252, the encoding legacy code was almost
 * always written in (spec/pairs-format.md).
 */
export function decode(raw: Uint8Array): string {
  try {
    return utf8Decoder.decode(raw);
  } catch {
    let text = "";
    for (const byte of raw) {
      text += String.fromCharCode(byte >= 0x80 && byte < 0xa0 ? WINDOWS_1252_HIGH[byte - 0x80]! : byte);
    }
    return text;
  }
}

/** Compares strings by code point, which is the byte order of their UTF-8 (spec/pairs-format.md). */
export function compareText(a: string, b: string): number {
  const length = Math.min(a.length, b.length);
  for (let index = 0; index < length; index++) {
    const left = a.charCodeAt(index);
    const right = b.charCodeAt(index);
    if (left !== right) {
      return codeUnitOrder(left) - codeUnitOrder(right);
    }
  }
  return a.length - b.length;
}

// UTF-16 puts surrogates (astral code points) before U+E000 to U+FFFF; moving them after
// gives code point order without decoding.
function codeUnitOrder(unit: number): number {
  if (unit >= 0xd800 && unit <= 0xdfff) {
    return unit + 0x2000;
  }
  return unit >= 0xe000 ? unit - 0x800 : unit;
}

export function sortText(items: Iterable<string>): string[] {
  return [...items].sort(compareText);
}

/** Collapses runs of whitespace to one space, for source text written into ids. */
export function collapse(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}
