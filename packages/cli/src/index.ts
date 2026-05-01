#!/usr/bin/env node
import { Command } from "commander";
import chalk from "chalk";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { runScan } from "./commands/scan.js";
import { runInit, printInitResult } from "./commands/init.js";
import { runDemo } from "./commands/demo.js";
import { runStatus } from "./commands/status.js";

const here: string = dirname(fileURLToPath(import.meta.url));
const pkg: { version: string } = JSON.parse(
  readFileSync(join(here, "..", "package.json"), "utf8"),
) as { version: string };

const program: Command = new Command();

program
  .name("clawos")
  .description("ClawOS — The AI Operating System for Companies")
  .version(pkg.version);

program
  .command("init")
  .description("Initialize a new ClawOS agent project in cwd")
  .option("--force", "Overwrite existing keypair", false)
  .action(async (opts: { force: boolean }) => {
    try {
      const result = await runInit({ force: opts.force });
      printInitResult(result);
    } catch (err) {
      console.error(chalk.red(`[clawos/cli] init failed: ${(err as Error).message}`));
      process.exit(1);
    }
  });

program
  .command("scan")
  .description("Score the agent config in the current working directory")
  .option("-c, --config <path>", "Path to clawos.config.json", "./clawos.config.json")
  .option("-t, --threshold <number>", "Pass/fail threshold", "60")
  .action(async (opts: { config: string; threshold: string }) => {
    const code = await runScan({
      configPath: opts.config,
      threshold: Number.parseInt(opts.threshold, 10),
    });
    process.exit(code);
  });

program
  .command("status")
  .description("Show the local ClawOS agent's pubkey, policy, and memory stats")
  .action(async () => {
    const code = await runStatus();
    process.exit(code);
  });

program
  .command("demo")
  .description("Run the ClawOS end-to-end demo flow in cwd")
  .option("-t, --threshold <number>", "Pass/fail threshold for the scan gate", "60")
  .action(async (opts: { threshold: string }) => {
    const code = await runDemo({ threshold: Number.parseInt(opts.threshold, 10) });
    process.exit(code);
  });

program.parse();
