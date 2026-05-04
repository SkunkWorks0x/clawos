// Real LLM synthesis for the oracle's closed-loop step. Calls Anthropic's
// Sonnet 4.6 with the swarm's reflection memos and returns a 1-2 sentence
// next-step. Returns null on missing key or any failure — pipeline keeps
// running on the simulated path so the demo still works offline.

import Anthropic from "@anthropic-ai/sdk";

export interface SynthesisInput {
  task: string;
  scanScore: number | null;
  scanFindings: number | null;
  flagged: boolean;
  priorMemos: string[];
}

const MODEL = "claude-sonnet-4-6";
const MAX_TOKENS = 150;
const TIMEOUT_MS = 5000;

export async function synthesizeNextStep(input: SynthesisInput): Promise<string | null> {
  if (!process.env.ANTHROPIC_API_KEY) return null;

  const client = new Anthropic({ timeout: TIMEOUT_MS, maxRetries: 0 });
  const prompt = buildPrompt(input);

  try {
    const response = await client.messages.create({
      model: MODEL,
      max_tokens: MAX_TOKENS,
      messages: [{ role: "user", content: prompt }],
    });
    for (const block of response.content) {
      if (block.type === "text") return block.text.trim();
    }
    return null;
  } catch {
    return null;
  }
}

function buildPrompt(input: SynthesisInput): string {
  const lines: string[] = [
    "You are the oracle agent in a multi-agent swarm. A session just finished.",
    "",
    `Task: ${input.task}`,
  ];
  if (input.scanScore !== null) {
    lines.push(`Sentinel scan: ${input.scanScore}/100, ${input.scanFindings ?? 0} finding(s).`);
  }
  if (input.flagged) {
    lines.push("Policy flagged elevated scope; masterchief approved with audit trail.");
  }
  if (input.priorMemos.length > 0) {
    lines.push("");
    lines.push("Prior memos (most recent first):");
    for (const m of input.priorMemos) lines.push(`- ${m}`);
  }
  lines.push("");
  lines.push("Synthesize the single next action in 1-2 short sentences. Be specific and operational. No preamble.");
  return lines.join("\n");
}
