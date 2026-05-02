import chalk from "chalk";
import { runSwarm } from "@clawos/orchestrator/swarm";

export interface SwarmArgs {
  task?: string;
  quiet?: boolean;
  cadenceMs?: number;
}

/** Run the multi-agent swarm pipeline with closed-loop reflection dispatch. */
export async function runSwarmCommand(args: SwarmArgs = {}): Promise<number> {
  try {
    const result = await runSwarm({
      task: args.task,
      quiet: args.quiet ?? false,
      cadenceMs: args.cadenceMs,
    });
    if (!args.quiet) {
      const blocked = result.steps.filter((s) => s.blocked).length;
      const flagged = result.steps.filter((s) => s.flagged).length;
      console.log(
        chalk.dim(
          `  ${result.steps.length + 1} dispatches · ${blocked} blocked · ${flagged} flagged · ${result.reflection.ids.length} reflection${result.reflection.ids.length === 1 ? "" : "s"}`,
        ),
      );
    }
    return result.steps.some((s) => s.blocked) || !result.followup.dispatched ? 1 : 0;
  } catch (err) {
    console.error(chalk.red(`[clawos/cli] swarm failed: ${(err as Error).message}`));
    return 1;
  }
}
