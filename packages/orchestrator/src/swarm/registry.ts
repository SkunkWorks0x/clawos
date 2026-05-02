// Agent registry — names map to capability profiles. Names are stable IDs
// used by the decomposer to route subtasks to specific agents.

export interface Agent {
  name: string;
  role: string;
  capabilities: string[];
}

export class AgentRegistry {
  private readonly agents = new Map<string, Agent>();

  register(agent: Agent): void {
    this.agents.set(agent.name, agent);
  }

  get(name: string): Agent | undefined {
    return this.agents.get(name);
  }

  has(name: string): boolean {
    return this.agents.has(name);
  }

  list(): Agent[] {
    return Array.from(this.agents.values());
  }

  size(): number {
    return this.agents.size;
  }
}

/** Five-agent default seed used by the swarm demo. */
export function defaultRegistry(): AgentRegistry {
  const r = new AgentRegistry();
  r.register({ name: "masterchief", role: "commander", capabilities: ["dispatch", "reflect"] });
  r.register({ name: "forge", role: "builder", capabilities: ["scaffold", "init"] });
  r.register({ name: "blade", role: "security", capabilities: ["scan", "audit"] });
  r.register({ name: "cortana", role: "intelligence", capabilities: ["analyze", "recall"] });
  r.register({ name: "arbiter", role: "policy", capabilities: ["evaluate", "approve"] });
  return r;
}
