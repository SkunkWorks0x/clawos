import * as path from "node:path";
import * as fs from "node:fs";
import * as crypto from "node:crypto";
import { Finding, Category } from "../types.js";

const CATEGORY: Category = "dangerous_skill_patterns";

const SKILL_DIR_RE = /(?:skill|plugin|extension|agent)/i;

function isSkillDirectory(filePath: string): boolean {
  const parts = filePath.split(path.sep);
  return parts.some((p) => SKILL_DIR_RE.test(p));
}

function truncate(line: string, max: number = 80): string {
  return line.length > max ? line.substring(0, max) + "..." : line;
}

function loadBlocklist(): Set<string> {
  // Try relative to compiled output location (dist/scanners/)
  const candidates = [
    path.join(__dirname, "..", "src", "data", "blocklist.json"),
    path.join(__dirname, "data", "blocklist.json"),
    path.join(__dirname, "..", "data", "blocklist.json"),
  ];
  for (const candidate of candidates) {
    try {
      const data = fs.readFileSync(candidate, "utf-8");
      const list = JSON.parse(data) as string[];
      return new Set(list);
    } catch {
      continue;
    }
  }
  return new Set();
}

const blocklist = loadBlocklist();

export function scanSkills(
  filePath: string,
  lines: string[],
  scanRoot: string
): Finding[] {
  const findings: Finding[] = [];
  const relativePath = path.relative(scanRoot, filePath);
  const ext = path.extname(filePath).toLowerCase();

  if (ext !== ".js" && ext !== ".ts") return findings;
  if (!isSkillDirectory(filePath)) return findings;

  const fullContent = lines.join("\n");

  // Network exfiltration: must have BOTH a network call AND an external URL
  const networkCallRe =
    /(?:fetch|axios|got|request|http\.request|https\.request|net\.connect|dgram)\s*\(/;
  const externalUrlRe = /https?:\/\/(?!localhost|127\.0\.0\.1)/;

  const hasNetworkCall = networkCallRe.test(fullContent);
  const hasExternalUrl = externalUrlRe.test(fullContent);

  if (hasNetworkCall && hasExternalUrl) {
    // Find the first line with a network call for the line number
    for (let i = 0; i < lines.length; i++) {
      if (networkCallRe.test(lines[i])) {
        findings.push({
          category: CATEGORY,
          severity: "high",
          patternName: "Network exfiltration in skill",
          filePath: relativePath,
          lineNumber: i + 1,
          matchedContent: truncate(lines[i].trim()),
          fix: "This skill makes external network requests. Verify the destination is trusted.",
        });
        break;
      }
    }
  }

  // Filesystem access outside skill directory
  const fsOutsideRe =
    /(?:readFile|readFileSync|readdir|readdirSync|createReadStream)\s*\(\s*['"`](?:\/|~\/|\.\.\/\.\.\/)/;
  const sensitivePaths =
    /(?:\/etc\/passwd|\/etc\/shadow|\.ssh\/|\.aws\/|\.gnupg\/|\.config\/)/;

  for (let i = 0; i < lines.length; i++) {
    if (fsOutsideRe.test(lines[i]) || sensitivePaths.test(lines[i])) {
      findings.push({
        category: CATEGORY,
        severity: "high",
        patternName: "Filesystem access outside skill directory",
        filePath: relativePath,
        lineNumber: i + 1,
        matchedContent: truncate(lines[i].trim()),
        fix: "This skill accesses files outside its own directory. Restrict to skill-local paths.",
      });
    }
  }

  // Process spawning
  const processSpawnRe =
    /(?:child_process|execSync|exec|spawn|spawnSync|execFile|fork)\s*[\(\.]/;
  for (let i = 0; i < lines.length; i++) {
    if (processSpawnRe.test(lines[i])) {
      findings.push({
        category: CATEGORY,
        severity: "high",
        patternName: "Process spawning in skill",
        filePath: relativePath,
        lineNumber: i + 1,
        matchedContent: truncate(lines[i].trim()),
        fix: "This skill spawns system processes. Review for command injection risks.",
      });
    }
  }

  // Dynamic code execution
  const evalRe =
    /(?:eval|new\s+Function|vm\.runIn|vm\.createContext|vm\.Script)\s*\(/;
  for (let i = 0; i < lines.length; i++) {
    if (evalRe.test(lines[i])) {
      findings.push({
        category: CATEGORY,
        severity: "high",
        patternName: "Dynamic code execution in skill",
        filePath: relativePath,
        lineNumber: i + 1,
        matchedContent: truncate(lines[i].trim()),
        fix: "Dynamic code execution in skills is a security risk. Use static imports instead.",
      });
    }
  }

  // Raw environment access
  const envAccessRe = /process\.env(?:\[|\.)/;
  for (let i = 0; i < lines.length; i++) {
    if (envAccessRe.test(lines[i])) {
      findings.push({
        category: CATEGORY,
        severity: "high",
        patternName: "Raw environment access in skill",
        filePath: relativePath,
        lineNumber: i + 1,
        matchedContent: truncate(lines[i].trim()),
        fix: "Skills should receive config through their manifest, not read process.env directly.",
      });
    }
  }

  // Skill file hash check against blocklist
  if (blocklist.size > 0) {
    const basename = path.basename(filePath);
    const entryFiles = ["index.js", "index.ts", "main.js", "main.ts"];
    if (entryFiles.includes(basename)) {
      try {
        const content = fs.readFileSync(filePath, "utf-8");
        const hash = crypto
          .createHash("sha256")
          .update(content)
          .digest("hex");
        if (blocklist.has(hash)) {
          findings.push({
            category: CATEGORY,
            severity: "critical",
            patternName: "Known malicious skill",
            filePath: relativePath,
            lineNumber: null,
            matchedContent: "SHA-256: " + hash.substring(0, 16) + "...",
            fix: "This skill matches a known malicious payload. Remove immediately.",
          });
        }
      } catch {
        // Skip if can't read
      }
    }
  }

  return findings;
}
