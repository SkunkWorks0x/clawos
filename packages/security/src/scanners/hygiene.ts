import * as path from "node:path";
import * as fs from "node:fs";
import { Finding, Category } from "../types.js";

const CATEGORY: Category = "hygiene";

export function scanHygiene(scanRoot: string): Finding[] {
  const findings: Finding[] = [];

  // Check for .gitignore existence
  const gitignorePath = path.join(scanRoot, ".gitignore");
  let gitignoreExists = false;
  let gitignoreContent = "";

  try {
    gitignoreContent = fs.readFileSync(gitignorePath, "utf-8");
    gitignoreExists = true;
  } catch {
    // Does not exist
  }

  if (!gitignoreExists) {
    findings.push({
      category: CATEGORY,
      severity: "medium",
      patternName: "Missing .gitignore",
      filePath: "(project root)",
      lineNumber: null,
      matchedContent: "No .gitignore file found",
      fix: "Add a .gitignore file. At minimum, exclude: node_modules, .env*, *.pem, *.key, dist/",
    });
  } else {
    // Check for critical entries
    const requiredPatterns: Array<{ pattern: string; display: string }> = [
      { pattern: ".env", display: ".env" },
      { pattern: "*.pem", display: "*.pem" },
      { pattern: "*.key", display: "*.key" },
    ];

    const missing: string[] = [];
    for (const req of requiredPatterns) {
      // Check if the gitignore contains the pattern (exact line or as part of a glob)
      const lines = gitignoreContent.split("\n").map((l) => l.trim());
      const found = lines.some((line) => {
        if (line.startsWith("#") || line === "") return false;
        // Check for exact match or glob that covers it
        return line === req.pattern || line === req.display;
      });
      if (!found) {
        missing.push(req.display);
      }
    }

    if (missing.length > 0) {
      findings.push({
        category: CATEGORY,
        severity: "medium",
        patternName: ".gitignore missing critical entries",
        filePath: ".gitignore",
        lineNumber: null,
        matchedContent: `Missing: ${missing.join(", ")}`,
        fix: "Add '.env', '*.pem', '*.key' to .gitignore to prevent accidental credential commits",
      });
    }
  }

  // Check for lockfile
  const lockfiles = [
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
  ];
  const hasLockfile = lockfiles.some((lf) => {
    try {
      fs.accessSync(path.join(scanRoot, lf));
      return true;
    } catch {
      return false;
    }
  });

  if (!hasLockfile) {
    findings.push({
      category: CATEGORY,
      severity: "low",
      patternName: "No lockfile",
      filePath: "(project root)",
      lineNumber: null,
      matchedContent: "No package-lock.json, yarn.lock, or pnpm-lock.yaml found",
      fix: "Commit a lockfile to prevent supply-chain attacks via dependency resolution",
    });
  }

  return findings;
}
