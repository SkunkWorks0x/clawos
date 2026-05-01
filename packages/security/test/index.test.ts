// @clawos/security public API tests — README contract: scan(input?) returns
// findings with `severity`, `check`, `message`, `remediation` aliases.

import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as path from "node:path";
import { scan } from "../src/index.js";

const PROJECT_ROOT = path.resolve(__dirname, "..", "..");
const FIXTURES_DIR = path.join(PROJECT_ROOT, "test", "fixtures");

describe("@clawos/security public API", () => {
  it("scan(string) returns findings with README aliases", () => {
    const result = scan(FIXTURES_DIR);
    assert.ok(result.findings.length > 0);
    for (const f of result.findings) {
      assert.strictEqual(typeof f.severity, "string");
      assert.strictEqual(typeof f.check, "string");
      assert.strictEqual(typeof f.message, "string");
      assert.strictEqual(typeof f.remediation, "string");
    }
  });

  it("scan(agentConfig) honors scanPath when provided", () => {
    const result = scan({ name: "test", threshold: 60, scanPath: FIXTURES_DIR });
    assert.ok(result.findings.length > 0);
    assert.ok(result.scanPath.endsWith("fixtures"));
  });

  it("scan(string) returns numeric score 0-100", () => {
    const result = scan(FIXTURES_DIR);
    assert.strictEqual(typeof result.score, "number");
    assert.ok(result.score >= 0 && result.score <= 100);
  });
});
