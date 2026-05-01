import { Finding, ScanResult, Severity, Category } from "./types.js";

// ANSI escape codes
const RED = "\x1b[31m";
const YELLOW = "\x1b[33m";
const CYAN = "\x1b[36m";
const WHITE = "\x1b[37m";
const GREEN = "\x1b[32m";
const BOLD = "\x1b[1m";
const RESET = "\x1b[0m";

function severityColor(severity: Severity): string {
  switch (severity) {
    case "critical":
      return RED;
    case "high":
      return YELLOW;
    case "medium":
      return CYAN;
    case "low":
      return WHITE;
  }
}

function severityTag(severity: Severity): string {
  const color = severityColor(severity);
  return `${color}${severity.toUpperCase()}${RESET}`;
}

const CATEGORY_HEADERS: Record<Category, string> = {
  credential_exposure: "CREDENTIAL EXPOSURE",
  dangerous_skill_patterns: "DANGEROUS SKILL PATTERNS",
  permission_configuration: "PERMISSION & CONFIGURATION",
  hygiene: "GITIGNORE & HYGIENE",
};

const CATEGORY_ORDER: Category[] = [
  "credential_exposure",
  "dangerous_skill_patterns",
  "permission_configuration",
  "hygiene",
];

function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

export function formatTerminalOutput(result: ScanResult): string {
  const lines: string[] = [];

  // Header
  lines.push(
    ""
  );
  lines.push(
    `${BOLD}\uD83E\uDD9E ClawStack Sentinel v0.1.0 \u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501${RESET}`
  );
  lines.push(
    `Scanning: ${result.scanPath}  Files scanned: ${formatNumber(result.filesScanned)} | Skipped: ${formatNumber(result.filesSkipped)} (node_modules, binary, >1MB)`
  );

  // Group findings by category
  const grouped = new Map<Category, Finding[]>();
  for (const cat of CATEGORY_ORDER) {
    grouped.set(cat, []);
  }
  for (const f of result.findings) {
    const arr = grouped.get(f.category);
    if (arr) arr.push(f);
  }

  // Output each category
  for (const cat of CATEGORY_ORDER) {
    const catFindings = grouped.get(cat)!;
    if (catFindings.length === 0) continue;

    lines.push("");
    lines.push(
      `${BOLD}\u2501\u2501\u2501\u2501\u2501\u2501 ${CATEGORY_HEADERS[cat]} \u2501\u2501\u2501\u2501\u2501\u2501${RESET}`
    );

    for (const f of catFindings) {
      const location = f.lineNumber !== null ? `${f.filePath}:${f.lineNumber}` : f.filePath;
      lines.push("");
      lines.push(`  ${severityTag(f.severity)}  ${f.patternName}`);
      lines.push(`    ${location}`);
      lines.push(`    ${f.matchedContent}`);
      lines.push(`    Fix: ${f.fix}`);
    }
  }

  // Score
  lines.push("");
  lines.push(
    `${BOLD}\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501${RESET}`
  );

  let bracketColor: string;
  if (result.score >= 90) {
    bracketColor = GREEN;
  } else if (result.score >= 70) {
    bracketColor = YELLOW;
  } else if (result.score >= 40) {
    bracketColor = RED;
  } else {
    bracketColor = `${BOLD}${RED}`;
  }

  lines.push(
    `  ${BOLD}SECURITY SCORE: ${bracketColor}${result.score} / 100 [${result.bracket}]${RESET}`
  );

  // Summary counts
  const counts = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const f of result.findings) {
    counts[f.severity]++;
  }
  const total = result.findings.length;
  lines.push(
    `  ${total} findings: ${counts.critical} critical \u00B7 ${counts.high} high \u00B7 ${counts.medium} medium \u00B7 ${counts.low} low`
  );

  if (total === 0) {
    lines.push(
      ""
    );
    lines.push(
      `  ${GREEN}No issues detected. If this seems wrong, make sure you're scanning the right directory.${RESET}`
    );
  }

  return lines.join("\n");
}
