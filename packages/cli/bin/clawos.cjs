#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");

const userCwd = process.env.INIT_CWD || process.cwd();
const cliRoot = path.resolve(__dirname, "..");
const candidates = [
  path.resolve(cliRoot, "node_modules", ".bin", "tsx"),
  path.resolve(cliRoot, "..", "..", "node_modules", ".bin", "tsx"),
];

let tsxBin = null;
for (const c of candidates) {
  if (fs.existsSync(c)) {
    tsxBin = c;
    break;
  }
}
if (!tsxBin) {
  console.error("[clawos] tsx not found; run `pnpm install` from the workspace root");
  process.exit(1);
}

const entry = path.resolve(cliRoot, "src", "index.ts");
const args = process.argv.slice(2);

const result = spawnSync(tsxBin, [entry, ...args], {
  stdio: "inherit",
  cwd: userCwd,
});
process.exit(result.status === null ? 1 : result.status);
