// @clawos/policy public API tests — README contract.
import { describe, it, expect } from "vitest";
import { evaluate } from "../../src/api.js";

const policy = {
  maxTransactionAmount: 500,
  dailySpendingLimit: 2000,
  allowedCounterparties: ["0xABC", "0xDEF"],
  restrictedHours: { block: false },
  multiSigThreshold: 1000,
};

describe("@clawos/policy evaluate", () => {
  it("allows a transaction within all limits", () => {
    const result = evaluate({ to: "0xABC", amount: 100 }, policy);
    expect(result.allow).toBe(true);
    expect(result.reason).toContain("within policy");
  });

  it("blocks when amount exceeds maxTransactionAmount", () => {
    const result = evaluate({ to: "0xABC", amount: 600 }, policy);
    expect(result.allow).toBe(false);
    expect(result.reason).toMatch(/max transaction/i);
    expect(result.remediation.length).toBeGreaterThan(0);
  });

  it("blocks counterparty not on the allowlist", () => {
    const result = evaluate({ to: "0xDEAD", amount: 100 }, policy);
    expect(result.allow).toBe(false);
    expect(result.reason).toMatch(/allowlist|allowed/i);
  });

  it("requires multi-sig at or above the threshold", () => {
    const policyWithLowThreshold = { ...policy, maxTransactionAmount: 5000, multiSigThreshold: 1000 };
    const result = evaluate({ to: "0xABC", amount: 1500 }, policyWithLowThreshold);
    expect(result.allow).toBe(false);
    expect(result.reason).toMatch(/multi-sig/i);
  });

  it("respects dailySpendingLimit when dailySpentSoFar is provided", () => {
    const result = evaluate(
      { to: "0xABC", amount: 100 },
      { ...policy, dailySpentSoFar: 1950 },
    );
    expect(result.allow).toBe(false);
    expect(result.reason).toMatch(/daily/i);
  });

  it("blocks outside business-hours window when restrictedHours.block is true", () => {
    const restricted = { ...policy, restrictedHours: { block: true, outside: "09:00-17:00" } };
    // ISO strings without offset are parsed as local time.
    const before = evaluate({ to: "0xABC", amount: 100, timestamp: "2026-05-01T03:30:00" }, restricted);
    const within = evaluate({ to: "0xABC", amount: 100, timestamp: "2026-05-01T14:30:00" }, restricted);
    expect(before.allow).toBe(false);
    expect(within.allow).toBe(true);
  });
});
