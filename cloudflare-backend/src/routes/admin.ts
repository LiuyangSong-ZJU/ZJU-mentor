import { assertAdminRequest, assertAdminTokenString } from "../utils/auth";
import { readJson } from "../utils/response";
import type { Env } from "../types";
import {
  deleteCommentRecord,
  deleteLinkRecord,
  deleteSiteFeedback,
  queryAdminSiteFeedback,
  queryAdminTeacherRankings,
  queryTeacherDetail,
} from "../services/adminService";

export async function handleAdminRoute(request: Request, env: Env, pathname: string) {
  const url = new URL(request.url);

  if (request.method === "POST" && pathname === "/api/admin/session") {
    const payload = await readJson<{ token?: string }>(request);
    assertAdminTokenString(payload.token || "", env);
    return { ok: true };
  }

  if (pathname.startsWith("/api/admin/")) {
    assertAdminRequest(request, env);
  }

  if (request.method === "GET" && pathname === "/api/admin/teachers") {
    return queryAdminTeacherRankings(
      env,
      url.searchParams.get("sort") || "reviews",
      url.searchParams.get("q") || "",
    );
  }

  if (request.method === "GET" && pathname === "/api/admin/feedback") {
    return queryAdminSiteFeedback(env);
  }

  const teacherMatch = pathname.match(/^\/api\/admin\/teachers\/([^/]+)$/);
  if (request.method === "GET" && teacherMatch) {
    return queryTeacherDetail(env, decodeURIComponent(teacherMatch[1]));
  }

  const commentMatch = pathname.match(/^\/api\/admin\/comments\/(\d+)$/);
  if (request.method === "DELETE" && commentMatch) {
    return deleteCommentRecord(env, Number(commentMatch[1]));
  }

  const linkMatch = pathname.match(/^\/api\/admin\/links\/(\d+)$/);
  if (request.method === "DELETE" && linkMatch) {
    return deleteLinkRecord(env, Number(linkMatch[1]));
  }

  const feedbackMatch = pathname.match(/^\/api\/admin\/feedback\/(\d+)$/);
  if (request.method === "DELETE" && feedbackMatch) {
    return deleteSiteFeedback(env, Number(feedbackMatch[1]));
  }

  return null;
}
