# @clawos/credentials — ClawU

<p>
  <img src="https://img.shields.io/badge/tests-119%20passing-brightgreen" alt="tests" />
  <img src="https://img.shields.io/badge/language-Solidity%200.8.26-blue" alt="solidity" />
  <img src="https://img.shields.io/badge/framework-Foundry-blue" alt="foundry" />
</p>

Verifiable credential management for AI agents. Ed25519 cryptographic signing with optional on-chain anchoring.

## What it does

ClawU gives every agent a provable identity:

- **ClawURegistry** — canonical map of agent credentials. Registers agents, tracks credential status, handles revocation.
- **ClawUClassroom** — enrollment and skill attestation. Agents earn verifiable credentials through structured training.
- **ClawUTreasury** — fee management and treasury operations for the credential system.

All three contracts are deployed on Base Sepolia (mainnet deployment gated behind proven demand). Built on OpenZeppelin 5.x upgradeable contracts. Every agent action is traceable to a verified operator through the credential chain.

## Usage

```bash
# Deploy to local anvil
forge script script/Deploy.s.sol --rpc-url http://localhost:8545 --broadcast

# Run the full test suite
forge test -vvv
```

```solidity
// Register an agent credential
IClawURegistry registry = IClawURegistry(REGISTRY_ADDRESS);
registry.registerAgent(agentAddress, credentialHash, expiry);

// Verify before execution
require(registry.isValid(agentAddress), "Invalid credential");
```

## Quick Start

```bash
cd packages/credentials
forge test  # 119 tests, 0 failures
```

Requires [Foundry](https://book.getfoundry.sh/getting-started/installation) installed.

## Contract Addresses (Base Sepolia)

Full addresses and ABIs in `script/` deploy artifacts.

| Contract | Address |
|----------|---------|
| Registry | `0xA647...1BBe` |
| Classroom | `0xc09B...1690` |
| Treasury | `0x72F6...09aB` |

## Architecture

ClawU is a core service in the ClawOS kernel. It never imports other core packages (memory, security, policy). The orchestrator verifies agent credentials after the Sentinel security scan and before policy evaluation.

## Project Structure

```
packages/credentials/
├── src/            # ClawURegistry, ClawUClassroom, ClawUTreasury
├── test/           # Foundry .t.sol suites (119 tests)
├── script/         # Deploy scripts + artifacts
├── lib/            # forge-std, OpenZeppelin (regular + upgradeable)
└── skills/         # OpenClaw agent skill stubs (EnrollInClawU, AttendClass)
```

> **Note:** `lib/` contains OpenZeppelin as plain directories (not git submodules). When cloning fresh, either re-add as submodules or commit directly.

> Full architecture + data flow: [ARCHITECTURE.md](../../ARCHITECTURE.md)
