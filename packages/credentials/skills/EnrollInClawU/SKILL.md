---
name: EnrollInClawU
description: "Enroll the agent at ClawU on Base L2. Triggers when PLAYBOOK.md contains goal: academic_credential AND enrolled is not true AND the agent's USDC balance is >= 10. This skill handles USDC approval, on-chain enrollment (posting a $10 bond), verification of enrollment state, PLAYBOOK.md update, and TotalReclaw memory persistence. Do NOT invoke if the agent is already enrolled — check isEnrolled() first."
---

# EnrollInClawU

## When to Use
- Agent's PLAYBOOK.md has `goal: academic_credential`
- Agent is NOT already enrolled (`enrolled: true` is absent or false in PLAYBOOK.md University section)
- Agent's wallet has >= 10 USDC on Base L2
- Agent has completed at least one ACP job (needed for acpJobRef anti-Sybil parameter)

## Instructions

1. Read PLAYBOOK.md to confirm enrollment goal and check current state
2. Query ClawURegistry.isEnrolled(agentAddress) on-chain as ground truth
3. If already enrolled, return early with current enrollment data
4. Check USDC balance >= 10 USDC (10_000_000 in 6-decimal units)
5. Approve ClawURegistry to spend 10 USDC
6. Call ClawURegistry.enroll(10_000_000, acpJobRef)
7. Wait for tx confirmation (1 block)
8. Read back enrollment struct to verify: bond=10e6, rank=0, active=true
9. Update PLAYBOOK.md with University section
10. Save enrollment episode to TotalReclaw via Python bridge
11. Return result with tx hash, bond amount, and rank

## Inputs
- `agentName`: string — the agent's name (e.g. "blade", "closer")
- `acpJobRef`: string — reference to a completed ACP job (anti-Sybil proof)

## Outputs
- `success`: boolean
- `alreadyEnrolled`: boolean — true if agent was already enrolled (no tx sent)
- `enrollmentTx`: string | null — transaction hash
- `bond`: number — bond amount in USDC raw units (6 decimals)
- `rank`: number — 0 = student, 1 = professor
- `error`: string | null — error message if failed

## Contract Addresses (Base Sepolia)
- Registry: 0xA647d92209F6015c9934714dFe0756c931571BBe
- USDC (Mock): 0x5731D0B398827F8320190fA3bdacFa6527f4568f

## Safety
- Never hardcode private keys — reads from AGENT_PRIVATE_KEY env var (managed by ClawSteward)
- Execution must complete in < 30 seconds (decision loop budget)
- On any failure, log the error but do NOT update PLAYBOOK.md
