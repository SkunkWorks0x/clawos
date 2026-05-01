#!/usr/bin/env node

import * as fs from "node:fs";
import * as path from "node:path";
import { scan } from "./scanner.js";
import { formatTerminalOutput } from "./formatter.js";
import { generateReport } from "./reporter.js";

function parseArgs(argv: string[]): {
  path: string;
  output: string;
  json: boolean;
} {
  const args = argv.slice(2);
  let scanPath = process.cwd();
  let output = "./sentinel-report.md";
  let json = false;

  // Skip the "audit" subcommand if present
  let i = 0;
  if (args[i] === "audit") {
    i++;
  }

  for (; i < args.length; i++) {
    switch (args[i]) {
      case "--path":
        i++;
        if (i < args.length) {
          scanPath = args[i];
        }
        break;
      case "--output":
        i++;
        if (i < args.length) {
          output = args[i];
        }
        break;
      case "--json":
        json = true;
        break;
    }
  }

  return { path: scanPath, output, json };
}

function main(): void {
  const config = parseArgs(process.argv);

  try {
    const result = scan(config.path);

    if (config.json) {
      process.stdout.write(JSON.stringify(result, null, 2) + "\n");
    } else {
      const terminalOutput = formatTerminalOutput(result);
      process.stdout.write(terminalOutput + "\n");

      // Generate and write report
      const report = generateReport(result);
      const reportPath = path.resolve(config.output);
      fs.writeFileSync(reportPath, report, "utf-8");
      process.stdout.write(`\n  Report saved: ${config.output}\n`);
      process.stdout.write(
        "\x1b[1m\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\x1b[0m\n"
      );
    }
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : String(err);

    if (message === "NOT_A_PROJECT") {
      process.stderr.write(
        "\u26A0 This directory doesn't appear to contain a project. Use --path to specify your OpenClaw project root.\n"
      );
      process.exit(1);
    }

    process.stderr.write(`Error: ${message}\n`);
    process.exit(1);
  }
}

main();
