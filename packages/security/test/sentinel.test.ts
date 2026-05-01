import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as path from "node:path";
import * as fs from "node:fs";
import * as child_process from "node:child_process";
import * as os from "node:os";
import { scan } from "../src/scanner.js";
import { generateReport } from "../src/reporter.js";

// __dirname in compiled output is dist/test/, project root is two levels up
const PROJECT_ROOT = path.resolve(__dirname, "..", "..");
const FIXTURES_DIR = path.join(PROJECT_ROOT, "test", "fixtures");
const CLI_PATH = path.join(PROJECT_ROOT, "dist", "src", "cli.js");

describe("ClawStack Sentinel Scanner", () => {
  it("should find at least 1 credential finding in fixtures", () => {
    const result = scan(FIXTURES_DIR);
    const credFindings = result.findings.filter(
      (f) => f.category === "credential_exposure"
    );
    assert.ok(
      credFindings.length >= 1,
      `Expected at least 1 credential finding, got ${credFindings.length}`
    );
  });

  it("should find at least 1 dangerous skill finding", () => {
    const result = scan(FIXTURES_DIR);
    const skillFindings = result.findings.filter(
      (f) => f.category === "dangerous_skill_patterns"
    );
    assert.ok(
      skillFindings.length >= 1,
      `Expected at least 1 skill finding, got ${skillFindings.length}`
    );
  });

  it("should find at least 1 permission finding", () => {
    const result = scan(FIXTURES_DIR);
    const permFindings = result.findings.filter(
      (f) => f.category === "permission_configuration"
    );
    assert.ok(
      permFindings.length >= 1,
      `Expected at least 1 permission finding, got ${permFindings.length}`
    );
  });

  it("should find at least 1 hygiene finding", () => {
    const result = scan(FIXTURES_DIR);
    const hygieneFindings = result.findings.filter(
      (f) => f.category === "hygiene"
    );
    assert.ok(
      hygieneFindings.length >= 1,
      `Expected at least 1 hygiene finding, got ${hygieneFindings.length}`
    );
  });

  it("should find at least 8 total findings", () => {
    const result = scan(FIXTURES_DIR);
    assert.ok(
      result.findings.length >= 8,
      `Expected at least 8 findings, got ${result.findings.length}`
    );
  });

  it("should score below 50 for the fixture directory", () => {
    const result = scan(FIXTURES_DIR);
    assert.ok(
      result.score < 50,
      `Expected score below 50, got ${result.score}`
    );
  });

  it("should output valid JSON when --json is used", () => {
    const output = child_process.execSync(
      `node ${CLI_PATH} audit --path ${FIXTURES_DIR} --json`,
      { encoding: "utf-8" }
    );
    const parsed = JSON.parse(output);
    assert.ok(parsed.scanPath, "JSON output should have scanPath");
    assert.ok(
      Array.isArray(parsed.findings),
      "JSON output should have findings array"
    );
    assert.ok(
      typeof parsed.score === "number",
      "JSON output should have numeric score"
    );
  });

  it("should generate a report containing ClawStack Sentinel", () => {
    const result = scan(FIXTURES_DIR);
    const report = generateReport(result);
    assert.ok(
      report.includes("ClawStack Sentinel"),
      "Report should contain 'ClawStack Sentinel'"
    );
    assert.ok(
      report.includes("Security Score"),
      "Report should contain 'Security Score'"
    );
  });

  it("should return score 100 for an empty project directory", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "sentinel-test-"));
    // Create a minimal package.json so it's recognized as a project
    // Also create a .gitignore with required entries and a lockfile
    fs.writeFileSync(
      path.join(tmpDir, "package.json"),
      '{"name":"empty-test"}',
      "utf-8"
    );
    fs.writeFileSync(
      path.join(tmpDir, ".gitignore"),
      ".env\n*.pem\n*.key\n",
      "utf-8"
    );
    fs.writeFileSync(
      path.join(tmpDir, "package-lock.json"),
      '{"lockfileVersion":3}',
      "utf-8"
    );
    try {
      const result = scan(tmpDir);
      assert.strictEqual(
        result.score,
        100,
        `Expected score 100 for empty project, got ${result.score}`
      );
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it("should default to scanning cwd when no --path is given", () => {
    const output = child_process.execSync(
      `node ${CLI_PATH} audit --json`,
      { encoding: "utf-8", cwd: FIXTURES_DIR }
    );
    const parsed = JSON.parse(output);
    assert.ok(
      parsed.scanPath.endsWith("fixtures"),
      `Expected scanPath to end with 'fixtures', got ${parsed.scanPath}`
    );
  });
});
