import type { Env } from "../types";
import { assertAdminRequest } from "../utils/auth";
import { readJson } from "../utils/response";
import { listSyncRuns, runDailyBigUnitSync, runFullSync, uploadLocalSnapshots } from "../services/syncService";

export async function handleIngestRoute(request: Request, env: Env, pathname: string) {
  if (!pathname.startsWith("/api/admin/sync")) {
    return null;
  }

  assertAdminRequest(request, env);

  if (request.method === "POST" && pathname === "/api/admin/sync/run") {
    return runFullSync(env, "manual-crawler");
  }

  if (request.method === "POST" && pathname === "/api/admin/sync/run-daily") {
    return runDailyBigUnitSync(env);
  }

  if (request.method === "POST" && pathname === "/api/admin/sync/upload-snapshots") {
    const payload = await readJson<Record<string, unknown>>(request);
    return uploadLocalSnapshots(env, payload);
  }

  if (request.method === "GET" && pathname === "/api/admin/sync/runs") {
    return listSyncRuns(env);
  }

  return null;
}
