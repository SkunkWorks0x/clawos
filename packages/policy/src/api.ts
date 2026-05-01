// @clawos/policy public API — README contract:
//   import { evaluate } from "@clawos/policy";
//   const result = evaluate(transaction, policySet);
//   // { allow: boolean, reason: string, remediation: string }
//
// Implements the simple JSON policy schema documented in packages/policy/README.md:
//   { maxTransactionAmount, dailySpendingLimit, allowedCounterparties,
//     restrictedHours: { block, outside? }, multiSigThreshold }
// Distinct from the ClawSteward chain-aware engine in src/core/ — that one
// requires SimulationResult input and is exposed via the MCP server.

export interface ClawosTransaction {
  to?: string;
  amount: number;
  action?: string;
  timestamp?: string;
}

export interface RestrictedHours {
  block: boolean;
  outside?: string;
}

export interface ClawosPolicySet {
  maxTransactionAmount?: number;
  dailySpendingLimit?: number;
  allowedCounterparties?: string[];
  restrictedHours?: RestrictedHours;
  multiSigThreshold?: number;
  dailySpentSoFar?: number;
}

export interface EvaluateResult {
  allow: boolean;
  reason: string;
  remediation: string;
}

const ALLOW: EvaluateResult = {
  allow: true,
  reason: "Transaction within policy",
  remediation: "",
};

/** Evaluate a transaction against a policy set. README schema. */
export function evaluate(
  transaction: ClawosTransaction,
  policySet: ClawosPolicySet,
): EvaluateResult {
  if (
    policySet.maxTransactionAmount !== undefined &&
    transaction.amount > policySet.maxTransactionAmount
  ) {
    return {
      allow: false,
      reason: `Amount ${transaction.amount} exceeds max transaction limit ${policySet.maxTransactionAmount}`,
      remediation: "Split into smaller transactions or raise the limit",
    };
  }

  if (
    policySet.dailySpendingLimit !== undefined &&
    (policySet.dailySpentSoFar ?? 0) + transaction.amount >
      policySet.dailySpendingLimit
  ) {
    return {
      allow: false,
      reason: `Daily spending limit ${policySet.dailySpendingLimit} would be exceeded`,
      remediation: "Wait until daily window resets or raise the daily limit",
    };
  }

  if (
    policySet.allowedCounterparties !== undefined &&
    policySet.allowedCounterparties.length > 0 &&
    transaction.to !== undefined &&
    !policySet.allowedCounterparties.includes(transaction.to)
  ) {
    return {
      allow: false,
      reason: `Counterparty ${transaction.to} is not in allowlist`,
      remediation: "Add the counterparty to allowedCounterparties or route through an allowed address",
    };
  }

  if (
    policySet.restrictedHours?.block === true &&
    !isWithinAllowedWindow(transaction.timestamp, policySet.restrictedHours.outside)
  ) {
    return {
      allow: false,
      reason: `Transactions blocked outside ${policySet.restrictedHours.outside ?? "allowed hours"}`,
      remediation: "Retry within the allowed window",
    };
  }

  if (
    policySet.multiSigThreshold !== undefined &&
    transaction.amount >= policySet.multiSigThreshold
  ) {
    return {
      allow: false,
      reason: `Amount ${transaction.amount} requires multi-sig (threshold ${policySet.multiSigThreshold})`,
      remediation: "Request multi-sig approval before executing",
    };
  }

  return ALLOW;
}

function isWithinAllowedWindow(
  timestamp: string | undefined,
  windowSpec: string | undefined,
): boolean {
  if (!windowSpec) return true;
  const match = /^(\d{2}):(\d{2})-(\d{2}):(\d{2})$/.exec(windowSpec);
  if (!match) return true;
  const startH = Number(match[1]);
  const startM = Number(match[2]);
  const endH = Number(match[3]);
  const endM = Number(match[4]);
  const now = timestamp ? new Date(timestamp) : new Date();
  if (Number.isNaN(now.getTime())) return true;
  const minutes = now.getHours() * 60 + now.getMinutes();
  const start = startH * 60 + startM;
  const end = endH * 60 + endM;
  if (start <= end) {
    return minutes >= start && minutes <= end;
  }
  return minutes >= start || minutes <= end;
}
