import * as path from "node:path";
import { Finding, Category } from "../types.js";

const CATEGORY: Category = "credential_exposure";

const PLACEHOLDER_RE = /^(your[_-]|placeholder|TODO|CHANGEME|xxx|example|test|fake|dummy|insert[_-]|replace[_-]|<[^>]+>|\$\{)/i;

function maskSecret(value: string): string {
  if (value.length <= 6) return "****";
  return value.substring(0, 4) + "****" + value.substring(value.length - 2);
}

function truncate(line: string, max: number = 120): string {
  return line.length > max ? line.substring(0, max) + "..." : line;
}

interface PatternMatch {
  patternName: string;
  severity: "critical" | "high";
  matchedContent: string;
  fix: string;
}

function matchLine(line: string): PatternMatch[] {
  const matches: PatternMatch[] = [];

  // AWS Access Key ID
  const awsKeyMatch = line.match(/AKIA[0-9A-Z]{16}/);
  if (awsKeyMatch) {
    matches.push({
      patternName: "AWS Access Key ID",
      severity: "critical",
      matchedContent: "Matched: " + maskSecret(awsKeyMatch[0]),
      fix: "Move AWS credentials to environment variables and add this file to .gitignore",
    });
  }

  // AWS Secret Key
  const awsSecretMatch = line.match(
    /(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY)['"]?\s*[=:]\s*['"]?([A-Za-z0-9/+=]{40})['"]?/
  );
  if (awsSecretMatch) {
    matches.push({
      patternName: "AWS Secret Access Key",
      severity: "critical",
      matchedContent: "Matched: " + maskSecret(awsSecretMatch[1]),
      fix: "Move AWS secret key to environment variables",
    });
  }

  // Generic API Key/Secret
  const apiKeyMatch = line.match(
    /(?:api[_-]?key|api[_-]?secret|secret[_-]?key|access[_-]?token|auth[_-]?token)['"]?\s*[=:]\s*['"]([^'"]{8,})['"]/i
  );
  if (apiKeyMatch) {
    const value = apiKeyMatch[1];
    if (!PLACEHOLDER_RE.test(value)) {
      matches.push({
        patternName: "Generic API Key/Secret",
        severity: "critical",
        matchedContent: "Matched: " + maskSecret(value),
        fix: "Move this secret to an environment variable",
      });
    }
  }

  // Database URIs with credentials
  const dbUriMatch = line.match(
    /(?:mongodb|postgres|postgresql|mysql|redis|amqp):\/\/[^:\s]+:[^@\s]+@/
  );
  if (dbUriMatch) {
    matches.push({
      patternName: "Database URI with credentials",
      severity: "critical",
      matchedContent: "Matched: " + truncate(dbUriMatch[0], 40) + "...",
      fix: "Use environment variables for database connection strings",
    });
  }

  // Private keys
  const privateKeyMatch = line.match(
    /-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/
  );
  if (privateKeyMatch) {
    matches.push({
      patternName: "Private Key",
      severity: "critical",
      matchedContent: "Matched: " + privateKeyMatch[0],
      fix: "Remove private keys from the codebase. Use a secrets manager or mount at runtime.",
    });
  }

  // JWT tokens
  const jwtMatch = line.match(
    /eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+/
  );
  if (jwtMatch) {
    matches.push({
      patternName: "Hardcoded JWT",
      severity: "critical",
      matchedContent: "Matched: " + maskSecret(jwtMatch[0]),
      fix: "Hardcoded JWTs should be removed. Generate tokens at runtime.",
    });
  }

  return matches;
}

export function scanCredentials(
  filePath: string,
  lines: string[],
  scanRoot: string
): Finding[] {
  const findings: Finding[] = [];
  const relativePath = path.relative(scanRoot, filePath);
  const basename = path.basename(filePath);

  // .env file check — flag the entire file if it has non-comment, non-empty lines with values
  const envMatch = basename.match(/^\.env(\..*)?$/);
  if (envMatch) {
    const contentLines = lines.filter((l) => {
      const trimmed = l.trim();
      if (!trimmed || trimmed.startsWith("#")) return false;
      const eqIndex = trimmed.indexOf("=");
      if (eqIndex === -1) return false;
      const value = trimmed.substring(eqIndex + 1).trim();
      return value.length > 0;
    });
    if (contentLines.length > 0) {
      findings.push({
        category: CATEGORY,
        severity: "high",
        patternName: ".env file with secrets",
        filePath: relativePath,
        lineNumber: null,
        matchedContent: `${contentLines.length} non-empty lines`,
        fix: "Ensure .env files are in .gitignore and never committed to version control",
      });
    }
  }

  // Check if this is a markdown file in a memory-like directory
  const dirName = path.dirname(filePath).toLowerCase();
  const isMemoryDir =
    /(?:memory|memories|context|identity)/.test(dirName) &&
    filePath.endsWith(".md");

  // Scan every line with credential patterns
  // For .md files, only scan if in memory-like directory OR it's not .md
  const ext = path.extname(filePath).toLowerCase();
  const shouldScanLines = ext !== ".md" || isMemoryDir;

  if (shouldScanLines) {
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const matches = matchLine(line);
      for (const m of matches) {
        findings.push({
          category: CATEGORY,
          severity: m.severity,
          patternName: m.patternName,
          filePath: relativePath,
          lineNumber: i + 1,
          matchedContent: m.matchedContent,
          fix: m.fix,
        });
      }
    }
  }

  return findings;
}
