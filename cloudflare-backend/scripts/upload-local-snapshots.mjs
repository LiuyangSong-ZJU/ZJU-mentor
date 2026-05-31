#!/usr/bin/env node
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const rootDir = resolve(dirname(new URL(import.meta.url).pathname), "..");
const repoRoot = resolve(rootDir, "..");
const dataDir = resolve(repoRoot, "data");

const args = new Set(process.argv.slice(2));
const targetUrl =
  process.env.ZJU_MENTOR_SYNC_URL ||
  process.env.ZJU_MENTOR_SITE_URL ||
  (args.has("--local") ? "http://127.0.0.1:8787" : "https://zjumentors.com");
const tokenPath = resolve(rootDir, ".prod-admin-token");
const adminToken =
  process.env.ZJU_MENTOR_ADMIN_TOKEN ||
  process.env.ADMIN_TOKEN ||
  (existsSync(tokenPath) ? readFileSync(tokenPath, "utf8").trim() : "");

const collegesPath = process.env.ZJU_MENTOR_COLLEGES_JSON || resolve(dataDir, "zju_colleges.json");
const teachersPath = process.env.ZJU_MENTOR_TEACHERS_JSON || resolve(dataDir, "all_zju_teachers.json");

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

if (!adminToken) {
  throw new Error("缺少后台 token：请设置 ZJU_MENTOR_ADMIN_TOKEN，或保留 cloudflare-backend/.prod-admin-token。");
}

const colleges = readJson(collegesPath);
const teachers = readJson(teachersPath);
const endpoint = `${targetUrl.replace(/\/$/, "")}/api/admin/sync/upload-snapshots`;

console.log(`准备上传本地快照到 ${endpoint}`);
console.log(`单位文件: ${collegesPath} (${colleges.length} 条)`);
console.log(`教师文件: ${teachersPath} (${teachers.length} 条)`);

const response = await fetch(endpoint, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Admin-Token": adminToken,
  },
  body: JSON.stringify({
    source: "local-mac-json",
    colleges,
    teachers,
  }),
});

const text = await response.text();
if (!response.ok) {
  throw new Error(`上传失败: HTTP ${response.status}\n${text}`);
}

console.log("上传并同步完成，后端返回：");
console.log(text);
