#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { gzipSync } from "node:zlib";

const DATABASE_NAME = "zju-mentor-db";
const FULL_TABLES = [
  "big_departments",
  "departments",
  "teachers",
  "teacher_department_relations",
  "comments",
  "cc98_links",
  "comment_votes",
  "site_feedback",
  "daily_visits",
  "sync_runs",
];
const PUBLIC_TABLES = [
  "big_departments",
  "departments",
  "teachers",
  "teacher_department_relations",
  "comments",
  "cc98_links",
];

const args = new Set(process.argv.slice(2));
const mode = args.has("--local") ? "local" : "remote";
const shouldPrune = !args.has("--no-prune");
const rootDir = resolve(dirname(new URL(import.meta.url).pathname), "..");
const backupsDir = resolve(rootDir, "backups");
const timestamp = new Date().toISOString().replace(/\.\d{3}Z$/, "Z").replaceAll(":", "-");
const backupDir = join(backupsDir, timestamp);
const fullJsonDir = join(backupDir, "json", "full");
const publicJsonDir = join(backupDir, "json", "public");

function run(command, commandArgs, options = {}) {
  const result = spawnSync(command, commandArgs, {
    cwd: rootDir,
    encoding: "utf8",
    maxBuffer: 200 * 1024 * 1024,
    stdio: options.capture ? ["ignore", "pipe", "pipe"] : "inherit",
  });

  if (result.status !== 0) {
    const stderr = result.stderr ? `\n${result.stderr}` : "";
    throw new Error(`${command} ${commandArgs.join(" ")} 执行失败。${stderr}`);
  }

  return result.stdout || "";
}

function wranglerArgs(...extraArgs) {
  return ["wrangler", ...extraArgs, mode === "local" ? "--local" : "--remote"];
}

function gzipFile(inputPath, outputPath) {
  const source = readFileSync(inputPath);
  writeFileSync(outputPath, gzipSync(source, { level: 9 }));
  rmSync(inputPath);
  return {
    bytes: readFileSync(outputPath).byteLength,
    sha256: createHash("sha256").update(readFileSync(outputPath)).digest("hex"),
  };
}

function exportSql(outputPath, tables = []) {
  const tableArgs = tables.flatMap((table) => ["--table", table]);
  run("npx", wranglerArgs("d1", "export", DATABASE_NAME, "--skip-confirmation", "--output", outputPath, ...tableArgs));
}

function queryTable(tableName) {
  const output = run(
    "npx",
    wranglerArgs("d1", "execute", DATABASE_NAME, "--json", "--command", `SELECT * FROM ${tableName}`),
    { capture: true },
  );
  const parsed = JSON.parse(output);
  return parsed?.[0]?.results || [];
}

function writeJsonTable(tableName, targetDir) {
  const rows = queryTable(tableName);
  const targetPath = join(targetDir, `${tableName}.json`);
  writeFileSync(targetPath, `${JSON.stringify(rows, null, 2)}\n`, "utf8");
  return rows.length;
}

function parseBackupDate(name) {
  const normalized = name.replaceAll("-", ":").replace(/^(\d{4}):(\d{2}):(\d{2})T/, "$1-$2-$3T");
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function pruneBackups() {
  if (!existsSync(backupsDir)) {
    return [];
  }

  const now = Date.now();
  const dayMs = 24 * 60 * 60 * 1000;
  const weekMs = 7 * 24 * 60 * 60 * 1000;
  const twoWeeksMs = 14 * dayMs;
  const twoMonthsMs = 62 * 24 * 60 * 60 * 1000;
  const oneYearMs = 365 * dayMs;
  const groups = new Map();
  const deleted = [];

  const backupEntries = readdirSync(backupsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => ({ name: entry.name, date: parseBackupDate(entry.name) }))
    .filter((entry) => entry.date)
    .sort((left, right) => right.date - left.date);

  for (const entry of backupEntries) {
    const age = now - entry.date.getTime();
    if (age <= twoWeeksMs) {
      continue;
    }

    let key;
    if (age <= twoMonthsMs) {
      key = `week-${Math.floor(entry.date.getTime() / weekMs)}`;
    } else if (age <= oneYearMs) {
      key = `month-${entry.date.getUTCFullYear()}-${String(entry.date.getUTCMonth() + 1).padStart(2, "0")}`;
    } else {
      key = `year-${entry.date.getUTCFullYear()}`;
    }

    if (!groups.has(key)) {
      groups.set(key, entry.name);
      continue;
    }

    rmSync(join(backupsDir, entry.name), { recursive: true, force: true });
    deleted.push(entry.name);
  }

  return deleted;
}

mkdirSync(fullJsonDir, { recursive: true });
mkdirSync(publicJsonDir, { recursive: true });

console.log(`开始生成 ${mode} 数据备份: ${backupDir}`);

const fullSqlPath = join(backupDir, "database-full.sql");
const publicSqlPath = join(backupDir, "database-public.sql");
exportSql(fullSqlPath);
exportSql(publicSqlPath, PUBLIC_TABLES);

const fullSqlArchive = gzipFile(fullSqlPath, `${fullSqlPath}.gz`);
const publicSqlArchive = gzipFile(publicSqlPath, `${publicSqlPath}.gz`);

const fullCounts = Object.fromEntries(FULL_TABLES.map((table) => [table, writeJsonTable(table, fullJsonDir)]));
const publicCounts = Object.fromEntries(PUBLIC_TABLES.map((table) => [table, writeJsonTable(table, publicJsonDir)]));

const manifest = {
  generatedAt: new Date().toISOString(),
  source: mode,
  database: DATABASE_NAME,
  restore: {
    fullSqlGzip: basename(`${fullSqlPath}.gz`),
    fullSqlGzipSha256: fullSqlArchive.sha256,
    fullTables: FULL_TABLES,
    fullTableCounts: fullCounts,
  },
  publicRelease: {
    publicSqlGzip: basename(`${publicSqlPath}.gz`),
    publicSqlGzipSha256: publicSqlArchive.sha256,
    publicTables: PUBLIC_TABLES,
    publicTableCounts: publicCounts,
    note: "公开包故意不包含 site_feedback、sync_runs 和 comment_votes，避免公开反馈内容与匿名投票标识。",
  },
};

writeFileSync(join(backupDir, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
writeFileSync(join(backupsDir, "latest-backup-path.txt"), `${backupDir}\n`, "utf8");

const deletedBackups = shouldPrune ? pruneBackups() : [];
console.log(`备份完成: ${backupDir}`);
console.log(`完整恢复 SQL: database-full.sql.gz (${fullSqlArchive.bytes} bytes)`);
console.log(`公开发布 SQL: database-public.sql.gz (${publicSqlArchive.bytes} bytes)`);
console.log("保留策略：14天内全留；14天到2个月每周留一份；2个月到1年每月留一份；1年以上每年留一份。");
console.log(`保留策略清理 ${deletedBackups.length} 个旧备份。`);
