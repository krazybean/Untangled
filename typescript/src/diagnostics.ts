// SPDX-License-Identifier: MIT
// Something Untangled tells the user about, as spec/diagnostics.md defines it: a level, a stable
// code for the condition, a message for people, and the project-relative files it is about.

export interface Diagnostic {
  level: "warning" | "error";
  code: string;
  message: string;
  /** Project-relative paths with `/`, in the order they are reported; absent when none is relevant. */
  files?: string[];
}

export function warningDiagnostic(code: string, message: string, files: string[] = []): Diagnostic {
  return files.length > 0 ? { level: "warning", code, message, files } : { level: "warning", code, message };
}

export function errorDiagnostic(code: string, message: string, files: string[] = []): Diagnostic {
  return files.length > 0 ? { level: "error", code, message, files } : { level: "error", code, message };
}

/** The JSON Lines form: one compact object, no line break, fields in the order of the spec. */
export function encodeDiagnostic(diagnostic: Diagnostic): string {
  const data: Diagnostic = { level: diagnostic.level, code: diagnostic.code, message: wellFormed(diagnostic.message) };
  if (diagnostic.files !== undefined && diagnostic.files.length > 0) {
    data.files = diagnostic.files.map(wellFormed);
  }
  return JSON.stringify(data);
}

/** The text form: `warning: <message>` or `error: <message>`, without the line break. */
export function diagnosticText(diagnostic: Diagnostic): string {
  return `${diagnostic.level}: ${diagnostic.message}`;
}

/** The messages of the warning diagnostics, for callers that read strings. */
export function warningMessages(diagnostics: Diagnostic[]): string[] {
  return diagnostics.filter((item) => item.level === "warning").map((item) => item.message);
}

/** The text with U+FFFD for what is not valid Unicode (a lone surrogate). */
function wellFormed(text: string): string {
  return text.replace(/\p{Cs}/gu, "�");
}
