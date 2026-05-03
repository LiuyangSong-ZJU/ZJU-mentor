import type { Env } from "../types";
import { AppError } from "./response";

function extractAdminToken(request: Request): string {
  const headerToken = (request.headers.get("X-Admin-Token") || "").trim();
  if (headerToken) {
    return headerToken;
  }

  const authorization = (request.headers.get("Authorization") || "").trim();
  if (authorization.toLowerCase().startsWith("bearer ")) {
    return authorization.slice(7).trim();
  }

  return "";
}

export function assertAdminRequest(request: Request, env: Env): void {
  const expected = (env.ADMIN_TOKEN || "").trim();
  if (!expected) {
    throw new AppError(401, "后台未启用。请先设置 Cloudflare Secret: ADMIN_TOKEN。");
  }

  const actual = extractAdminToken(request);
  if (actual !== expected) {
    throw new AppError(401, "后台口令错误。");
  }
}

export function assertAdminTokenString(token: string, env: Env): void {
  const expected = (env.ADMIN_TOKEN || "").trim();
  if (!expected) {
    throw new AppError(401, "后台未启用。请先设置 Cloudflare Secret: ADMIN_TOKEN。");
  }

  if (token.trim() !== expected) {
    throw new AppError(401, "后台口令错误。");
  }
}
