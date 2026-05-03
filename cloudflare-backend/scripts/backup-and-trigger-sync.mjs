#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";

const args = new Set(process.argv.slice(2));
const mode = args.has("--local") ? "local" : "remote";
const rootDir = resolve(dirname(new URL(import.meta.url).pathname), "..");
const syncUrl = process.env.ZJU_MENTOR_SYNC_URL || (mode === "local" ? "http://127.0.0.1:8787" : "");
const adminToken = process.env.ZJU_MENTOR_ADMIN_TOKEN || process.env.ADMIN_TOKEN || "";

function run(command, commandArgs) {
  const result = spawnSync(command, commandArgs, {
    cwd: rootDir,
    encoding: "utf8",
    stdio: "inherit",
  });

  if (result.status !== 0) {
    throw new Error(`${command} ${commandArgs.join(" ")} 执行失败。`);
  }
}

if (!syncUrl) {
  throw new Error("请设置 ZJU_MENTOR_SYNC_URL，例如 https://your-domain.example.com");
}

if (!adminToken) {
  throw new Error("请设置 ZJU_MENTOR_ADMIN_TOKEN。");
}

run("node", ["./scripts/create-data-backup.mjs", mode === "local" ? "--local" : "--remote"]);

const response = await fetch(`${syncUrl.replace(/\/$/, "")}/api/admin/sync/run`, {
  method: "POST",
  headers: {
    "X-Admin-Token": adminToken,
  },
});

const text = await response.text();
if (!response.ok) {
  throw new Error(`同步触发失败: HTTP ${response.status}\n${text}`);
}

console.log("同步已触发，后端返回：");
console.log(text);
