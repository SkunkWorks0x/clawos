import chalk from "chalk";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { scan, type PublicScanResult, type AgentConfig } from "@clawos/security";

export interface ScanCommandArgs {
  configPath: string;
  threshold: number;
}

/** Run Sentinel against the cwd. Returns the process exit code. */
export async function runScan(args: ScanCommandArgs): Promise<number> {
  const configAbs = resolve(args.configPath);
  let config: AgentConfig | undefined;
  if (existsSync(configAbs)) {
    try {
      config = JSON.parse(readFileSync(configAbs, "utf8")) as AgentConfig;
    } catch (err) {
      console.error(chalk.red(`[clawos/cli] Failed to parse ${configAbs}: ${(err as Error).message}`));
      return 1;
    }
  } else {
    console.warn(chalk.yellow(`[clawos/cli] No config at ${configAbs} — scanning cwd anyway`));
  }

  const result = scan(config);
  printResult(result, args.threshold, config);
  return result.score >= args.threshold ? 0 : 1;
}

function printResult(
  result: PublicScanResult,
  threshold: number,
  config: AgentConfig | undefined,
): void {
  const scoreLine = colorScore(result.score);
  const status = result.score >= threshold ? chalk.green("PASS") : chalk.red("FAIL");
  console.log("");
  console.log(chalk.bold(`Sentinel scan — ${result.scanPath}`));
  if (config?.name) console.log(`  agent:     ${config.name}`);
  console.log(`  files:     ${result.filesScanned} scanned, ${result.filesSkipped} skipped`);
  console.log(`  score:     ${scoreLine} / 100   threshold ${threshold}   ${status}`);
  console.log(`  bracket:   ${result.bracket}`);
  console.log(`  findings:  ${result.findings.length}`);
  if (result.findings.length > 0) {
    console.log("");
    console.log(chalk.bold("  severity   check                              message"));
    console.log("  ────────   ─────────────────────────────────  ─────────────────────────────");
    for (const f of result.findings.slice(0, 25)) {
      const sev = colorSeverity(f.severity).padEnd(10 + 10);
      const check = f.check.slice(0, 33).padEnd(33);
      const msg = f.message.length > 60 ? f.message.slice(0, 57) + "..." : f.message;
      console.log(`  ${sev} ${check}  ${msg}`);
    }
    if (result.findings.length > 25) {
      console.log(chalk.gray(`  …${result.findings.length - 25} more findings omitted`));
    }
  }
  console.log("");
}

function colorScore(score: number): string {
  if (score >= 80) return chalk.green(String(score));
  if (score >= 50) return chalk.yellow(String(score));
  return chalk.red(String(score));
}

function colorSeverity(sev: string): string {
  switch (sev) {
    case "critical":
      return chalk.red.bold(sev);
    case "high":
      return chalk.red(sev);
    case "medium":
      return chalk.yellow(sev);
    case "low":
      return chalk.gray(sev);
    default:
      return sev;
  }
}
