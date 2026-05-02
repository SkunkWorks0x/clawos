// @clawos/orchestrator/swarm — multi-agent swarm subsystem.
// Only files under this directory may import from @clawos/security,
// @clawos/policy, and the @clawos/memory shim.

export { AgentRegistry, defaultRegistry } from "./registry.js";
export type { Agent } from "./registry.js";
export { decompose, followupSubtask, FOLLOWUP_AGENT } from "./decompose.js";
export type { Subtask } from "./decompose.js";
export { SwarmShim } from "./shim.js";
export type { ShimConfig, ShimResponse } from "./shim.js";
export { SwarmLogger } from "./log.js";
export type { LogOptions } from "./log.js";
export { runSwarm } from "./pipeline.js";
export type { SwarmOptions, SwarmResult, SwarmStep } from "./pipeline.js";
