// Task decomposer — splits a high-level task into ordered subtasks tagged
// to specific agents. Deliberately not over-engineered: the simulateLLM
// helper returns a deterministic canned plan and never touches a network.

export interface Subtask {
  agent: string;
  action: string;
  description: string;
  amount: number;
  elevated: boolean;
}

/** Deterministic LLM stub. NEVER calls a real model. */
function simulateLLM(prompt: string): string {
  if (prompt.toLowerCase().includes("demo")) {
    return "forge:scaffold,blade:scan,masterchief:approve";
  }
  return "masterchief:dispatch";
}

export function decompose(task: string): Subtask[] {
  const plan = simulateLLM(task);
  return plan.split(",").map((item, idx): Subtask => {
    const [agent, action] = item.split(":") as [string, string];
    return {
      agent,
      action,
      description: `${agent}: ${action}`,
      // Tier the amounts to make the timeline visually distinct.
      amount: idx === 1 ? 250 : 100,
      // Exactly one subtask trips the visible policy flag.
      elevated: agent === "blade",
    };
  });
}

export const FOLLOWUP_AGENT = "oracle";

/** The single follow-up subtask dispatched after reflection. */
export function followupSubtask(): Subtask {
  return {
    agent: FOLLOWUP_AGENT,
    action: "synthesize",
    description: "oracle: synthesize next-step from reflection",
    amount: 50,
    elevated: false,
  };
}
