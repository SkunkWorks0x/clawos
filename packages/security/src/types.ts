export type Severity = "critical" | "high" | "medium" | "low";

export type Category =
  | "credential_exposure"
  | "dangerous_skill_patterns"
  | "permission_configuration"
  | "hygiene";

export interface Finding {
  category: Category;
  severity: Severity;
  patternName: string;
  filePath: string;
  lineNumber: number | null;
  matchedContent: string;
  fix: string;
}

export interface ScanResult {
  scanPath: string;
  filesScanned: number;
  filesSkipped: number;
  findings: Finding[];
  score: number;
  bracket: string;
  timestamp: string;
}
