// Swarm logger — chalk-driven terminal output tuned for Loom recording on
// macOS iTerm2. Padded agent column for alignment, sleep cadence between
// lines for visual rhythm, no emoji checkmarks (chalk green ✓ keeps cols).

import chalk from "chalk";

export interface LogOptions {
  quiet?: boolean;
  cadenceMs?: number;
}

const COL_WIDTH = 14; // padEnd width: "masterchief" = 11, gives clean alignment

export class SwarmLogger {
  private readonly opts: Required<LogOptions>;

  constructor(opts: LogOptions = {}) {
    this.opts = {
      quiet: opts.quiet ?? false,
      cadenceMs: opts.cadenceMs ?? 90,
    };
  }

  private write(line: string): void {
    if (this.opts.quiet) return;
    process.stdout.write(line + "\n");
  }

  private async pulse(): Promise<void> {
    if (this.opts.cadenceMs > 0) {
      await new Promise((r) => setTimeout(r, this.opts.cadenceMs));
    }
  }

  async header(title: string, sessionId: string): Promise<void> {
    this.write("");
    this.write(chalk.bold(title));
    this.write(chalk.dim(`  session ${sessionId}  ${new Date().toISOString()}`));
    this.write("");
    await this.pulse();
  }

  async step(agent: string, label: string, ms?: number): Promise<void> {
    const tick = chalk.green("✓");
    const name = chalk.cyan(agent.padEnd(COL_WIDTH));
    const timing = ms !== undefined ? chalk.dim(` (${ms.toFixed(1)}ms)`) : "";
    this.write(`  ${tick} ${name} ${label}${timing}`);
    await this.pulse();
  }

  async flag(label: string): Promise<void> {
    this.write(`  ${chalk.yellow("⚠")} ${chalk.yellow(label)}`);
    await this.pulse();
  }

  async followup(label: string): Promise<void> {
    this.write("");
    this.write(`  ${chalk.magenta("↻")} ${chalk.magenta(label)}`);
    await this.pulse();
  }

  async summary(line: string): Promise<void> {
    this.write("");
    this.write(chalk.bold.green(line));
    this.write("");
  }

  async note(line: string): Promise<void> {
    this.write(`  ${chalk.dim(line)}`);
    await this.pulse();
  }
}
