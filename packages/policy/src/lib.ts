// Library entry — re-exports the @clawos/policy public API without the
// CLI-bootstrapping side effects in src/index.ts.

export { evaluate } from "./api.js";
export type {
  ClawosTransaction,
  ClawosPolicySet,
  RestrictedHours,
  EvaluateResult,
} from "./api.js";
