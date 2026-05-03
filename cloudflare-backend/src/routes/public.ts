import type { Env } from "../types";
import { readJson } from "../utils/response";
import {
  createTeacherLink,
  createTeacherReview,
  createSiteFeedback,
  queryAllTeachersGroupedByInitial,
  queryGroupedColleges,
  queryPortalStats,
  queryTeacherDetail,
  queryTeacherSearch,
  queryTeacherSuggestions,
  queryUnitDetail,
  voteComment,
} from "../services/publicService";

export async function handlePublicRoute(request: Request, env: Env, pathname: string) {
  const url = new URL(request.url);

  if (request.method === "GET" && pathname === "/api/units") {
    return queryGroupedColleges(env);
  }

  if (request.method === "GET" && pathname === "/api/teachers/by-name") {
    return queryAllTeachersGroupedByInitial(env);
  }

  if (request.method === "GET" && pathname === "/api/stats") {
    return queryPortalStats(env);
  }

  if (request.method === "POST" && pathname === "/api/feedback") {
    const payload = await readJson<Record<string, unknown>>(request);
    return createSiteFeedback(env, payload);
  }

  if (request.method === "GET" && pathname === "/api/teachers/suggest") {
    return queryTeacherSuggestions(env, url.searchParams.get("q") || "");
  }

  if (request.method === "GET" && pathname === "/api/teachers/search") {
    return queryTeacherSearch(env, url.searchParams.get("q") || "");
  }

  const unitTeacherMatch = pathname.match(/^\/api\/units\/([^/]+)\/teachers$/);
  if (request.method === "GET" && unitTeacherMatch) {
    return queryUnitDetail(env, decodeURIComponent(unitTeacherMatch[1]));
  }

  const teacherDetailMatch = pathname.match(/^\/api\/teachers\/([^/]+)$/);
  if (request.method === "GET" && teacherDetailMatch) {
    return queryTeacherDetail(env, decodeURIComponent(teacherDetailMatch[1]));
  }

  const commentMatch = pathname.match(/^\/api\/teachers\/([^/]+)\/comments$/);
  if (request.method === "POST" && commentMatch) {
    const payload = await readJson<Record<string, unknown>>(request);
    return createTeacherReview(env, decodeURIComponent(commentMatch[1]), payload);
  }

  const voteMatch = pathname.match(/^\/api\/comments\/(\d+)\/vote$/);
  if (request.method === "POST" && voteMatch) {
    const payload = await readJson<Record<string, unknown>>(request);
    return voteComment(env, Number(voteMatch[1]), payload);
  }

  const linkMatch = pathname.match(/^\/api\/teachers\/([^/]+)\/links$/);
  if (request.method === "POST" && linkMatch) {
    const payload = await readJson<Record<string, unknown>>(request);
    return createTeacherLink(env, decodeURIComponent(linkMatch[1]), payload);
  }

  return null;
}
