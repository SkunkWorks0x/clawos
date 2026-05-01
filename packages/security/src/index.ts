// @clawos/security public API.
// Wraps the underlying directory scanner with the README-shaped contract:
//   import { scan } from "@clawos/security";
//   const result = scan(agentConfig); // or scan(path) or scan()
// Findings carry both internal field names and README aliases.

import { scan as scanDirectory } from "./scanner.js";
import type { Finding, ScanResult } from "./types.js";

export interface PublicFinding extends Finding {
  check: string;
  message: string;
  remediation: string;
}

export interface PublicScanResult extends Omit<ScanResult, "findings"> {
  findings: PublicFinding[];
}

export interface AgentConfig {
  name?: string;
  threshold?: number;
  scanPath?: string;
  [key: string]: unknown;
}

export type ScanInput = string | AgentConfig | undefined;

/** Run the Sentinel scanner. Accepts a path, an agent config, or nothing (cwd). */
export function scan(input?: ScanInput): PublicScanResult {
  const scanPath = resolveScanPath(input);
  const raw = scanDirectory(scanPath);
  const findings: PublicFinding[] = raw.findings.map(toPublicFinding);
  return { ...raw, findings };
}

function resolveScanPath(input: ScanInput): string {
  if (typeof input === "string") return input;
  if (input && typeof input === "object" && typeof input.scanPath === "string") {
    return input.scanPath;
  }
  return process.cwd();
}

function toPublicFinding(f: Finding): PublicFinding {
  const location = f.lineNumber !== null ? `${f.filePath}:${f.lineNumber}` : f.filePath;
  return {
    ...f,
    check: f.patternName,
    message: `${f.matchedContent} (${location})`,
    remediation: f.fix,
  };
}

export type { Finding, ScanResult, Severity, Category } from "./types.js";
