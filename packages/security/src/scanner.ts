import * as fs from "node:fs";
import * as path from "node:path";
import { Finding, ScanResult } from "./types.js";
import { scanCredentials } from "./scanners/credentials.js";
import { scanSkills } from "./scanners/skills.js";
import {
  scanPermissions,
  checkFilePermissions,
  checkRunningAsRoot,
} from "./scanners/permissions.js";
import { scanHygiene } from "./scanners/hygiene.js";
import { calculateScore } from "./scoring.js";

const SKIP_DIRS = new Set([
  "node_modules",
  ".git",
  "dist",
  "build",
  ".next",
  "__pycache__",
  "test",
]);

const MAX_FILE_SIZE = 1_000_000; // 1MB

function isBinary(buffer: Buffer, bytesRead: number): boolean {
  const bytesToCheck = Math.min(bytesRead, 512);
  for (let i = 0; i < bytesToCheck; i++) {
    if (buffer[i] === 0) return true;
  }
  return false;
}

function isProjectDirectory(dirPath: string): boolean {
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });
    for (const entry of entries) {
      const name = entry.name.toLowerCase();
      if (name === "package.json") return true;
      if (name === ".git") return true;
      if (name.endsWith(".md")) return true;
      if (name.endsWith(".js") || name.endsWith(".ts")) return true;
      if (name.endsWith(".json") || name.endsWith(".yaml") || name.endsWith(".yml")) return true;
      if (name.endsWith(".toml") || name.startsWith(".env")) return true;
      if (name.startsWith("docker-compose")) return true;
    }
  } catch {
    // Can't read directory
  }
  return false;
}

interface WalkResult {
  files: string[];
  skipped: number;
}

function walkDirectory(dirPath: string): WalkResult {
  const files: string[] = [];
  let skipped = 0;

  function walk(currentPath: string): void {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(currentPath, { withFileTypes: true });
    } catch {
      return; // Permission denied or other error
    }

    for (const entry of entries) {
      const fullPath = path.join(currentPath, entry.name);

      // Skip symlinks
      if (entry.isSymbolicLink()) {
        skipped++;
        continue;
      }

      if (entry.isDirectory()) {
        if (SKIP_DIRS.has(entry.name)) {
          // Count skipped directory contents (approximate)
          try {
            skipped += countEntriesRecursive(fullPath);
          } catch {
            skipped++;
          }
          continue;
        }
        walk(fullPath);
        continue;
      }

      if (!entry.isFile()) {
        skipped++;
        continue;
      }

      // Check file size
      try {
        const stat = fs.statSync(fullPath);
        if (stat.size > MAX_FILE_SIZE) {
          skipped++;
          continue;
        }
        if (stat.size === 0) {
          skipped++;
          continue;
        }
      } catch {
        skipped++;
        continue;
      }

      // Check for binary
      try {
        const fd = fs.openSync(fullPath, "r");
        const buf = Buffer.alloc(512);
        const bytesRead = fs.readSync(fd, buf, 0, 512, 0);
        fs.closeSync(fd);
        if (isBinary(buf, bytesRead)) {
          skipped++;
          continue;
        }
      } catch {
        skipped++;
        continue;
      }

      files.push(fullPath);
    }
  }

  walk(dirPath);
  return { files, skipped };
}

function countEntriesRecursive(dirPath: string): number {
  let count = 0;
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });
    for (const entry of entries) {
      count++;
      if (entry.isDirectory() && !entry.isSymbolicLink()) {
        count += countEntriesRecursive(path.join(dirPath, entry.name));
      }
    }
  } catch {
    // Ignore errors
  }
  return count;
}

export function scan(scanPath: string): ScanResult {
  const absPath = path.resolve(scanPath);

  // Validate directory
  if (!fs.existsSync(absPath) || !fs.statSync(absPath).isDirectory()) {
    throw new Error(`Directory not found: ${absPath}`);
  }

  if (!isProjectDirectory(absPath)) {
    throw new Error(
      "NOT_A_PROJECT"
    );
  }

  const findings: Finding[] = [];

  // Runtime check: running as root
  const rootFinding = checkRunningAsRoot();
  if (rootFinding) {
    findings.push(rootFinding);
  }

  // Walk directory
  const { files, skipped } = walkDirectory(absPath);

  // Scan each file
  for (const filePath of files) {
    let content: string;
    try {
      content = fs.readFileSync(filePath, "utf-8");
    } catch {
      continue; // Permission denied
    }

    const lines = content.split("\n");

    // Credential scanning
    const credFindings = scanCredentials(filePath, lines, absPath);
    findings.push(...credFindings);

    // Skill scanning
    const skillFindings = scanSkills(filePath, lines, absPath);
    findings.push(...skillFindings);

    // Permission/config scanning
    const permFindings = scanPermissions(filePath, lines, absPath);
    findings.push(...permFindings);

    // File permission check
    const filePermFinding = checkFilePermissions(filePath, absPath);
    if (filePermFinding) {
      findings.push(filePermFinding);
    }
  }

  // Hygiene checks
  const hygieneFindings = scanHygiene(absPath);
  findings.push(...hygieneFindings);

  // Calculate score
  const { score, bracket } = calculateScore(findings);

  return {
    scanPath: absPath,
    filesScanned: files.length,
    filesSkipped: skipped,
    findings,
    score,
    bracket,
    timestamp: new Date().toISOString(),
  };
}
