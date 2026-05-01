import { Finding } from "./types.js";

export interface ScoreResult {
  score: number;
  bracket: string;
}

export function calculateScore(findings: Finding[]): ScoreResult {
  let criticalDeductions = 0;
  let highDeductions = 0;
  let mediumDeductions = 0;
  let lowDeductions = 0;

  for (const f of findings) {
    switch (f.severity) {
      case "critical":
        criticalDeductions += 15;
        break;
      case "high":
        highDeductions += 8;
        break;
      case "medium":
        mediumDeductions += 4;
        break;
      case "low":
        lowDeductions += 2;
        break;
    }
  }

  // Apply caps
  criticalDeductions = Math.min(criticalDeductions, 60);
  highDeductions = Math.min(highDeductions, 30);
  mediumDeductions = Math.min(mediumDeductions, 20);
  lowDeductions = Math.min(lowDeductions, 10);

  const totalDeduction =
    criticalDeductions + highDeductions + mediumDeductions + lowDeductions;
  const score = Math.max(0, 100 - totalDeduction);

  let bracket: string;
  if (score >= 90) {
    bracket = "HARDENED";
  } else if (score >= 70) {
    bracket = "MODERATE RISK";
  } else if (score >= 40) {
    bracket = "HIGH RISK";
  } else {
    bracket = "CRITICAL RISK";
  }

  return { score, bracket };
}
