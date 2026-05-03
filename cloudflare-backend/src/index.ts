import { handleAdminRoute } from "./routes/admin";
import { handleIngestRoute } from "./routes/ingest";
import { handlePublicRoute } from "./routes/public";
import type { Env } from "./types";
import { errorResponse, handleOptions, json } from "./utils/response";
import { runScheduledSync } from "./services/syncService";

async function routeRequest(request: Request, env: Env): Promise<Response> {
  const { pathname } = new URL(request.url);

  if (request.method === "OPTIONS") {
    return handleOptions();
  }

  if (pathname.startsWith("/api/")) {
    const ingestPayload = await handleIngestRoute(request, env, pathname);
    if (ingestPayload) {
      return json(ingestPayload);
    }

    const adminPayload = await handleAdminRoute(request, env, pathname);
    if (adminPayload) {
      return json(adminPayload);
    }

    const publicPayload = await handlePublicRoute(request, env, pathname);
    if (publicPayload) {
      return json(publicPayload);
    }

    return json({ message: "接口不存在。" }, 404);
  }

  if (env.ASSETS) {
    return env.ASSETS.fetch(request);
  }

  return json({ message: "资源不存在。" }, 404);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    try {
      return await routeRequest(request, env);
    } catch (error) {
      return errorResponse(error);
    }
  },

  async scheduled(_controller: ScheduledController, env: Env, ctx: ExecutionContext) {
    ctx.waitUntil(runScheduledSync(env));
  },
};
