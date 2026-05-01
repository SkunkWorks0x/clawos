import * as path from "node:path";
import * as fs from "node:fs";
import { Finding, Category } from "../types.js";

const CATEGORY: Category = "permission_configuration";

function truncate(line: string, max: number = 80): string {
  return line.length > max ? line.substring(0, max) + "..." : line;
}

const CONFIG_EXTENSIONS = new Set([
  ".json",
  ".yaml",
  ".yml",
  ".toml",
  ".env",
  ".conf",
  ".cfg",
  ".ini",
]);

function isConfigFile(filePath: string): boolean {
  const ext = path.extname(filePath).toLowerCase();
  const basename = path.basename(filePath).toLowerCase();
  return CONFIG_EXTENSIONS.has(ext) || basename.startsWith(".env");
}

function isDockerFile(filePath: string): boolean {
  const basename = path.basename(filePath).toLowerCase();
  return (
    basename.startsWith("docker-compose") || basename.startsWith("dockerfile")
  );
}

export function scanPermissions(
  filePath: string,
  lines: string[],
  scanRoot: string
): Finding[] {
  const findings: Finding[] = [];
  const relativePath = path.relative(scanRoot, filePath);

  // Docker misconfigurations
  if (isDockerFile(filePath)) {
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      if (/privileged:\s*true/.test(line)) {
        findings.push({
          category: CATEGORY,
          severity: "critical",
          patternName: "Docker privileged mode",
          filePath: relativePath,
          lineNumber: i + 1,
          matchedContent: truncate(line.trim()),
          fix: "Remove privileged mode. Use specific capabilities instead.",
        });
      }

      if (/network_mode:\s*["']?host["']?/.test(line)) {
        findings.push({
          category: CATEGORY,
          severity: "high",
          patternName: "Docker host networking",
          filePath: relativePath,
          lineNumber: i + 1,
          matchedContent: truncate(line.trim()),
          fix: "Use bridge networking with explicit port mapping.",
        });
      }

      if (/\/var\/run\/docker\.sock/.test(line)) {
        findings.push({
          category: CATEGORY,
          severity: "critical",
          patternName: "Docker socket mounted",
          filePath: relativePath,
          lineNumber: i + 1,
          matchedContent: truncate(line.trim()),
          fix: "Docker socket mounting gives full host control. Remove unless absolutely required.",
        });
      }

      if (/^\s*-\s*["']?\/(etc|root|home)/.test(line)) {
        findings.push({
          category: CATEGORY,
          severity: "high",
          patternName: "Sensitive host directory mounted",
          filePath: relativePath,
          lineNumber: i + 1,
          matchedContent: truncate(line.trim()),
          fix: "Restrict volume mounts to project directories only.",
        });
      }
    }
  }

  // Config file checks
  if (isConfigFile(filePath)) {
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      if (/(?:host|bind|listen|address)['"]?\s*[=:]\s*['"]?0\.0\.0\.0['"]?/.test(line)) {
        findings.push({
          category: CATEGORY,
          severity: "high",
          patternName: "Exposed network binding",
          filePath: relativePath,
          lineNumber: i + 1,
          matchedContent: truncate(line.trim()),
          fix: "Binding to 0.0.0.0 exposes the service to all network interfaces. Use 127.0.0.1 for local-only access.",
        });
      }

      if (
        /(?:sandbox|sandboxing|isolation)['"]?\s*[=:]\s*['"]?(?:false|off|disabled|none|0)['"]?/i.test(
          line
        )
      ) {
        findings.push({
          category: CATEGORY,
          severity: "high",
          patternName: "Sandboxing disabled",
          filePath: relativePath,
          lineNumber: i + 1,
          matchedContent: truncate(line.trim()),
          fix: "Enable sandboxing for agent execution.",
        });
      }

      if (
        /(?:auth|authentication|auth_required|require_auth)['"]?\s*[=:]\s*['"]?(?:false|off|disabled|none|0)['"]?/i.test(
          line
        )
      ) {
        findings.push({
          category: CATEGORY,
          severity: "critical",
          patternName: "Authentication disabled",
          filePath: relativePath,
          lineNumber: i + 1,
          matchedContent: truncate(line.trim()),
          fix: "Enable authentication. Unauthenticated access is the #1 attack vector (ref: CVE-2026-25253).",
        });
      }
    }
  }

  return findings;
}

export function checkFilePermissions(
  filePath: string,
  scanRoot: string
): Finding | null {
  const basename = path.basename(filePath).toLowerCase();
  const sensitivePatterns = [
    /\.env/,
    /\.pem$/,
    /\.key$/,
    /\.p12$/,
    /\.pfx$/,
    /\.jks$/,
    /^id_rsa/,
    /^id_ed25519/,
  ];

  const isSensitive = sensitivePatterns.some((re) => re.test(basename));
  if (!isSensitive) return null;

  try {
    const stat = fs.statSync(filePath);
    const mode = stat.mode;
    if ((mode & 0o044) !== 0) {
      return {
        category: "permission_configuration",
        severity: "medium",
        patternName: "World-readable sensitive file",
        filePath: path.relative(scanRoot, filePath),
        lineNumber: null,
        matchedContent: `Permissions: 0${(mode & 0o777).toString(8)}`,
        fix: `Restrict file permissions: chmod 600 ${path.basename(filePath)}`,
      };
    }
  } catch {
    // Skip if can't stat
  }

  return null;
}

export function checkRunningAsRoot(): Finding | null {
  if (
    typeof process.getuid === "function" &&
    process.getuid() === 0
  ) {
    return {
      category: "permission_configuration",
      severity: "critical",
      patternName: "Running as root",
      filePath: "(runtime check)",
      lineNumber: null,
      matchedContent: "Scanner detected UID 0 (root)",
      fix: "Never run OpenClaw agents as root. Create a dedicated user: sudo useradd -r -s /bin/false openclaw",
    };
  }
  return null;
}
