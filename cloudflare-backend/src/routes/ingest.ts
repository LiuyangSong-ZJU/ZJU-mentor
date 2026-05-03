import type { Env } from "../types";
import { assertAdminRequest } from "../utils/auth";
import { listSyncRuns, runFullSync } from "../services/syncService";

export async function handleIngestRoute(request: Request, env: Env, pathname: string) {
  if (!pathname.startsWith("/api/admin/sync")) {
    return null;
  }

  assertAdminRequest(request, env);

  if (request.method === "POST" && pathname === "/api/admin/sync/run") {
    return runFullSync(env, "manual-crawler");
  }

  if (request.method === "GET" && pathname === "/api/admin/sync/runs") {
    return { runs: await listSyncRuns(env) };
  }

  return null;
}
