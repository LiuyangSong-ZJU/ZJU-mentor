import { d1All, d1First, d1Run, METRIC_FIELDS } from "../db/queries";
import type { Env } from "../types";
import { AppError } from "../utils/response";
import {
  bigUnitSortKey,
  compactText,
  coerceScore,
  getTeacherInitial,
  normalizeText,
  teacherPinyin,
  UNASSIGNED_UNIT_NAME,
} from "../utils/normalize";

type TeacherRow = {
  uid: string;
  name: string;
  work_title: string | null;
  department: string | null;
  mapping_name: string | null;
  profile_url: string | null;
  college_id: string | null;
  college_name: string | null;
  big_unit_name: string | null;
};

function averageMetricValues(metricValues: Array<number | null>): number {
  const values = metricValues.filter((value): value is number => typeof value === "number");
  if (values.length === 0) {
    return 0;
  }

  const total = values.reduce((sum, value) => sum + value, 0);
  return Math.round((total / values.length) * 10) / 10;
}

export async function queryUnitRows(env: Env) {
  return d1All<{
    college_id: string;
    college_name: string;
    big_dept_id: string | null;
    big_unit_name: string;
    is_unassigned: number;
  }>(
    env.DB,
    `
      SELECT
        d.college_id AS college_id,
        d.college_name AS college_name,
        d.big_dept_id AS big_dept_id,
        COALESCE(b.name, ?) AS big_unit_name,
        CASE WHEN d.big_dept_id IS NULL THEN 1 ELSE 0 END AS is_unassigned
      FROM departments d
      LEFT JOIN big_departments b ON d.big_dept_id = b.id
      ORDER BY d.college_name
    `,
    [UNASSIGNED_UNIT_NAME],
  );
}

export async function queryGroupedColleges(env: Env) {
  const rows = await queryUnitRows(env);
  const groups = new Map<string, Array<{ collegeId: string; collegeName: string }>>();
  const hiddenColleges: Array<{ collegeId: string; collegeName: string }> = [];

  for (const row of rows) {
    const collegeItem = {
      collegeId: row.college_id,
      collegeName: row.college_name,
    };

    if (row.is_unassigned) {
      hiddenColleges.push(collegeItem);
      continue;
    }

    const current = groups.get(row.big_unit_name) || [];
    current.push(collegeItem);
    groups.set(row.big_unit_name, current);
  }

  if (hiddenColleges.length > 0) {
    const current = groups.get(UNASSIGNED_UNIT_NAME) || [];
    current.push(...hiddenColleges);
    groups.set(UNASSIGNED_UNIT_NAME, current);
  }

  const sortedGroupNames = [...groups.keys()].sort((left, right) => {
    const [leftIndex, leftName] = bigUnitSortKey(left);
    const [rightIndex, rightName] = bigUnitSortKey(right);
    return leftIndex - rightIndex || leftName.localeCompare(rightName, "zh-Hans-CN");
  });

  return {
    groups: sortedGroupNames.map((groupName) => ({
      bigUnitName: groupName,
      colleges: groups.get(groupName) || [],
    })),
    totalColleges: rows.length,
  };
}

export async function fetchTeacherRows(env: Env, collegeId?: string) {
  const binds: unknown[] = [UNASSIGNED_UNIT_NAME];
  let collegeFilterSql = "";

  if (collegeId) {
    collegeFilterSql = `
      WHERE t.uid IN (
        SELECT teacher_uid
        FROM teacher_department_relations
        WHERE college_id = ?
      )
    `;
    binds.push(collegeId);
  }

  const rows = await d1All<TeacherRow>(
    env.DB,
    `
      SELECT
        t.uid AS uid,
        t.name AS name,
        t.work_title AS work_title,
        t.department AS department,
        t.mapping_name AS mapping_name,
        t.profile_url AS profile_url,
        d.college_id AS college_id,
        d.college_name AS college_name,
        COALESCE(b.name, ?) AS big_unit_name
      FROM teachers t
      LEFT JOIN teacher_department_relations r ON t.uid = r.teacher_uid
      LEFT JOIN departments d ON r.college_id = d.college_id
      LEFT JOIN big_departments b ON d.big_dept_id = b.id
      ${collegeFilterSql}
      ORDER BY t.name, d.college_name
    `,
    binds,
  );

  const teachers = new Map<string, any>();
  for (const row of rows) {
    if (!teachers.has(row.uid)) {
      teachers.set(row.uid, {
        uid: row.uid,
        name: row.name,
        workTitle: row.work_title || "",
        department: row.department || "",
        mappingName: row.mapping_name || "",
        profileUrl: row.profile_url || "",
        initial: getTeacherInitial(row.name),
        colleges: [],
      });
    }

    if (row.college_id && row.college_name) {
      const teacher = teachers.get(row.uid);
      const collegeItem = {
        collegeId: row.college_id,
        collegeName: row.college_name,
        bigUnitName: row.big_unit_name || UNASSIGNED_UNIT_NAME,
      };

      const exists = teacher.colleges.some((item: any) => item.collegeId === collegeItem.collegeId);
      if (!exists) {
        teacher.colleges.push(collegeItem);
      }
    }
  }

  return [...teachers.values()];
}

function groupTeachersByInitial(teachers: any[]) {
  const grouped = new Map<string, any[]>();

  for (const teacher of teachers) {
    const initial = teacher.initial || "#";
    const current = grouped.get(initial) || [];
    current.push(teacher);
    grouped.set(initial, current);
  }

  const letters = Array.from({ length: 26 }, (_, index) => String.fromCharCode(65 + index)).concat("#");
  const sections = [];
  for (const letter of letters) {
    const items = grouped.get(letter);
    if (!items || items.length === 0) {
      continue;
    }

    items.sort((left, right) => left.name.localeCompare(right.name, "zh-Hans-CN"));
    sections.push({ letter, teachers: items });
  }

  return sections;
}

function teacherQueryScore(teacher: any, rawQuery: string): number | null {
  const queryCompact = compactText(rawQuery);
  if (!queryCompact) {
    return null;
  }

  const name = teacher.name || "";
  const nameCompact = compactText(name);
  const { full, initials } = teacherPinyin(name);
  const searchable = compactText(
    [
      teacher.workTitle || "",
      teacher.department || "",
      ...(teacher.colleges || []).map((college: any) => college.collegeName || ""),
    ].join(" "),
  );

  if (nameCompact.startsWith(queryCompact)) {
    return 0;
  }
  if (initials.startsWith(queryCompact)) {
    return 1;
  }
  if (initials.includes(queryCompact)) {
    return 2;
  }
  if (full.startsWith(queryCompact)) {
    return 3;
  }
  if (full.includes(queryCompact)) {
    return 4;
  }
  if (nameCompact.includes(queryCompact)) {
    return 5;
  }
  if (searchable.includes(queryCompact)) {
    return 8;
  }

  return null;
}

export async function queryAllTeachersGroupedByInitial(env: Env) {
  const teachers = await fetchTeacherRows(env);
  return {
    sections: groupTeachersByInitial(teachers),
    totalTeachers: teachers.length,
  };
}

export async function queryPortalStats(env: Env) {
  const settings = await querySiteSettings(env);
  const submittedTeacherRow = await d1First<Record<string, unknown>>(
    env.DB,
    `
      SELECT COUNT(*) AS submitted_teacher_count
      FROM (
        SELECT teacher_uid FROM comments
        UNION
        SELECT teacher_uid FROM cc98_links
      )
    `,
  );
  const reviewRow = await d1First<Record<string, unknown>>(
    env.DB,
    `
      SELECT
        COUNT(*) AS review_count
      FROM comments
    `,
  );
  const linkRow = await d1First<Record<string, unknown>>(
    env.DB,
    "SELECT COUNT(*) AS link_count FROM cc98_links",
  );

  return {
    isVisible: settings.showPortalStats,
    reviewedTeacherCount: Number(submittedTeacherRow?.submitted_teacher_count || 0),
    reviewCount: Number(reviewRow?.review_count || 0),
    linkCount: Number(linkRow?.link_count || 0),
  };
}

export async function querySiteSettings(env: Env) {
  const settingKeys = [
    "show_portal_stats",
    "show_discussion_group",
    "author_contact_mode",
    "show_about_links",
    "show_data_download",
  ];
  const rows = await d1All<Record<string, unknown>>(
    env.DB,
    `SELECT key, value FROM site_settings WHERE key IN (${settingKeys.map(() => "?").join(", ")})`,
    settingKeys,
  );
  const settings = new Map(rows.map((row) => [String(row.key), String(row.value)]));
  const contactMode = settings.get("author_contact_mode") === "direct" ? "direct" : "form";

  return {
    showPortalStats: settings.get("show_portal_stats") === "true",
    showDiscussionGroup: settings.get("show_discussion_group") === "true",
    authorContactMode: contactMode,
    showAboutLinks: settings.get("show_about_links") === "true",
    showDataDownload: settings.get("show_data_download") === "true",
  };
}

export async function updateSiteSettings(env: Env, payload: Record<string, unknown>) {
  const currentSettings = await querySiteSettings(env);
  const nextSettings = {
    showPortalStats:
      typeof payload.showPortalStats === "boolean" ? payload.showPortalStats : currentSettings.showPortalStats,
    showDiscussionGroup:
      typeof payload.showDiscussionGroup === "boolean" ? payload.showDiscussionGroup : currentSettings.showDiscussionGroup,
    authorContactMode: payload.authorContactMode === "direct" ? "direct" : payload.authorContactMode === "form" ? "form" : currentSettings.authorContactMode,
    showAboutLinks:
      typeof payload.showAboutLinks === "boolean" ? payload.showAboutLinks : currentSettings.showAboutLinks,
    showDataDownload:
      typeof payload.showDataDownload === "boolean" ? payload.showDataDownload : currentSettings.showDataDownload,
  };

  const settingsToWrite = [
    ["show_portal_stats", nextSettings.showPortalStats ? "true" : "false"],
    ["show_discussion_group", nextSettings.showDiscussionGroup ? "true" : "false"],
    ["author_contact_mode", nextSettings.authorContactMode],
    ["show_about_links", nextSettings.showAboutLinks ? "true" : "false"],
    ["show_data_download", nextSettings.showDataDownload ? "true" : "false"],
  ];

  for (const [key, value] of settingsToWrite) {
    await d1Run(
      env.DB,
      `
        INSERT INTO site_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
          value = excluded.value,
          updated_at = CURRENT_TIMESTAMP
      `,
      [key, value],
    );
  }

  return querySiteSettings(env);
}

function todayKeyInChina() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

export async function recordTodayVisit(env: Env, payload: Record<string, unknown>) {
  const visitorId = String(payload.visitorId || "").trim();
  if (!visitorId || visitorId.length > 128) {
    throw new AppError(400, "缺少有效的访问标识。");
  }

  const visitDate = todayKeyInChina();
  await d1Run(
    env.DB,
    "INSERT OR IGNORE INTO daily_visits (visit_date, visitor_id) VALUES (?, ?)",
    [visitDate, visitorId],
  );

  const row = await d1First<Record<string, unknown>>(
    env.DB,
    "SELECT COUNT(*) AS today_visits FROM daily_visits WHERE visit_date = ?",
    [visitDate],
  );

  return {
    date: visitDate,
    todayVisits: Number(row?.today_visits || 0),
  };
}

export async function queryUnitDetail(env: Env, collegeId: string) {
  const rows = await queryUnitRows(env);
  const targetCollege = rows.find((row) => row.college_id === collegeId);
  if (!targetCollege) {
    throw new AppError(404, `找不到单位: ${collegeId}`);
  }

  const teachers = await fetchTeacherRows(env, collegeId);
  return {
    college: {
      collegeId: targetCollege.college_id,
      collegeName: targetCollege.college_name,
      bigUnitName: targetCollege.big_unit_name,
    },
    sections: groupTeachersByInitial(teachers),
    totalTeachers: teachers.length,
  };
}

export async function queryTeacherSuggestions(env: Env, rawQuery: string) {
  const results = await queryTeacherSearch(env, rawQuery);
  const merged = [...results.exactMatches, ...results.fuzzyMatches];
  return {
    query: rawQuery,
    suggestions: merged.slice(0, 10).map((teacher) => ({
      uid: teacher.uid,
      name: teacher.name,
      workTitle: teacher.workTitle,
      colleges: teacher.colleges,
    })),
  };
}

export async function queryTeacherSearch(env: Env, rawQuery: string) {
  const query = normalizeText(rawQuery);
  const queryCompact = compactText(rawQuery);
  if (!queryCompact) {
    return {
      query: rawQuery,
      exactMatches: [],
      fuzzyMatches: [],
    };
  }

  const teachers = await fetchTeacherRows(env);
  const exactMatches: any[] = [];
  const fuzzyPool: Array<{ score: number; teacher: any }> = [];

  for (const teacher of teachers) {
    const nameLower = normalizeText(teacher.name || "");
    const nameCompact = compactText(teacher.name || "");

    if (nameLower === query || nameCompact === queryCompact) {
      exactMatches.push(teacher);
      continue;
    }

    const score = teacherQueryScore(teacher, rawQuery);
    if (score !== null) {
      fuzzyPool.push({ score, teacher });
    }
  }

  exactMatches.sort((left, right) => normalizeText(left.name).localeCompare(normalizeText(right.name), "zh-Hans-CN"));
  fuzzyPool.sort((left, right) => {
    return (
      left.score - right.score ||
      normalizeText(left.teacher.name).localeCompare(normalizeText(right.teacher.name), "zh-Hans-CN")
    );
  });

  return {
    query: rawQuery,
    exactMatches,
    fuzzyMatches: fuzzyPool.map((item) => item.teacher),
  };
}

function serializeReviewRow(row: Record<string, unknown>) {
  const reviewScores = [];
  for (const metric of METRIC_FIELDS) {
    const value = row[metric.column];
    if (value === null || value === undefined) {
      continue;
    }

    reviewScores.push({
      key: metric.key,
      label: metric.shortLabel,
      value: Number(value),
    });
  }

  return {
    id: Number(row.id),
    date: String(row.created_at || ""),
    identity: String(row.identity || ""),
    content: String(row.content || ""),
    isRunAway: Boolean(row.is_run_away),
    scores: reviewScores,
    upvotes: Number(row.upvotes || 0),
    downvotes: Number(row.downvotes || 0),
  };
}

export async function queryTeacherReviews(env: Env, uid: string) {
  const rows = await d1All<Record<string, unknown>>(
    env.DB,
    `
      SELECT
        id,
        identity,
        content,
        score_ethics,
        score_academic,
        score_wlb,
        score_funding,
        score_graduation,
        score_outcome,
        is_run_away,
        upvotes,
        downvotes,
        created_at
      FROM comments
      WHERE teacher_uid = ?
      ORDER BY datetime(created_at) DESC, id DESC
    `,
    [uid],
  );

  return rows.map(serializeReviewRow);
}

export async function queryTeacherLinks(env: Env, uid: string) {
  const rows = await d1All<Record<string, unknown>>(
    env.DB,
    `
      SELECT
        id,
        url,
        COALESCE(link_type, 'cc98') AS link_type,
        COALESCE(description, title, '') AS description,
        created_at
      FROM cc98_links
      WHERE teacher_uid = ?
      ORDER BY datetime(created_at) DESC, id DESC
    `,
    [uid],
  );

  return rows.map((row) => ({
    id: Number(row.id),
    url: String(row.url || ""),
    linkType: String(row.link_type || "cc98"),
    description: String(row.description || ""),
    date: String(row.created_at || ""),
  }));
}

export async function queryTeacherSummary(env: Env, uid: string) {
  const reviewCounts = await d1First<Record<string, unknown>>(
    env.DB,
    `
      SELECT
        COUNT(*) AS total_votes,
        SUM(CASE WHEN is_run_away = 1 THEN 1 ELSE 0 END) AS run_away_votes
      FROM comments
      WHERE teacher_uid = ?
    `,
    [uid],
  );

  const aggregates = await d1First<Record<string, unknown>>(
    env.DB,
    `
      SELECT
        AVG(score_ethics) AS avg_ethics,
        COUNT(score_ethics) AS count_ethics,
        AVG(score_academic) AS avg_academic,
        COUNT(score_academic) AS count_academic,
        AVG(score_wlb) AS avg_wlb,
        COUNT(score_wlb) AS count_wlb,
        AVG(score_funding) AS avg_funding,
        COUNT(score_funding) AS count_funding,
        AVG(score_graduation) AS avg_graduation,
        COUNT(score_graduation) AS count_graduation,
        AVG(score_outcome) AS avg_outcome,
        COUNT(score_outcome) AS count_outcome
      FROM comments
      WHERE teacher_uid = ?
    `,
    [uid],
  );

  const metrics = METRIC_FIELDS.map((metric) => {
    const average = Number(aggregates?.[`avg_${metric.key}`] ?? 0);
    const count = Number(aggregates?.[`count_${metric.key}`] ?? 0);
    return {
      key: metric.key,
      label: metric.label,
      shortLabel: metric.shortLabel,
      value: count > 0 ? Math.round(average * 10) / 10 : 0,
      votes: count,
    };
  });

  return {
    metrics,
    runAwayVotes: Number(reviewCounts?.run_away_votes || 0),
    totalVotes: Number(reviewCounts?.total_votes || 0),
  };
}

async function teacherExists(env: Env, uid: string): Promise<boolean> {
  const row = await d1First<{ uid: string }>(env.DB, "SELECT uid FROM teachers WHERE uid = ?", [uid]);
  return Boolean(row);
}

export async function queryTeacherDetail(env: Env, uid: string) {
  const teachers = await fetchTeacherRows(env);
  const teacher = teachers.find((item) => item.uid === uid);
  if (!teacher) {
    throw new AppError(404, `找不到导师: ${uid}`);
  }

  const summary = await queryTeacherSummary(env, uid);
  const reviews = await queryTeacherReviews(env, uid);
  const links = await queryTeacherLinks(env, uid);

  return {
    ...teacher,
    summary,
    reviews,
    links,
    runAwayVotes: summary.runAwayVotes,
    totalVotes: summary.totalVotes,
  };
}

export async function createTeacherReview(env: Env, uid: string, payload: Record<string, unknown>) {
  const scores = (payload.scores || {}) as Record<string, unknown>;
  const identity = String(payload.identity || "").trim();
  const content = String(payload.content || "").trim();
  const isRunAway = Boolean(payload.isRunAway);

  if (!(await teacherExists(env, uid))) {
    throw new AppError(404, `找不到导师: ${uid}`);
  }

  await d1Run(
    env.DB,
    `
      INSERT INTO comments (
        teacher_uid,
        identity,
        content,
        score_ethics,
        score_academic,
        score_wlb,
        score_funding,
        score_graduation,
        score_outcome,
        is_run_away
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
    [
      uid,
      identity,
      content,
      coerceScore(scores.ethics),
      coerceScore(scores.academic),
      coerceScore(scores.wlb),
      coerceScore(scores.funding),
      coerceScore(scores.graduation),
      coerceScore(scores.outcome),
      isRunAway ? 1 : 0,
    ],
  );

  return queryTeacherDetail(env, uid);
}

export async function createTeacherLink(env: Env, uid: string, payload: Record<string, unknown>) {
  const url = String(payload.url || "").trim();
  const rawType = String(payload.linkType || "cc98").trim().toLowerCase();
  const description = String(payload.description || "").trim();
  const linkType = rawType === "other" ? "other" : "cc98";

  if (!url) {
    throw new AppError(400, "链接不能为空。");
  }

  if (!(await teacherExists(env, uid))) {
    throw new AppError(404, `找不到导师: ${uid}`);
  }

  await d1Run(
    env.DB,
    `
      INSERT INTO cc98_links (
        teacher_uid,
        url,
        title,
        link_type,
        description
      ) VALUES (?, ?, ?, ?, ?)
    `,
    [uid, url, description || null, linkType, description],
  );

  return queryTeacherDetail(env, uid);
}

export async function createSiteFeedback(env: Env, payload: Record<string, unknown>) {
  const rawType = String(payload.feedbackType || "suggestion").trim().toLowerCase();
  const feedbackType = rawType === "error" ? "error" : "suggestion";
  const content = String(payload.content || "").trim();

  if (!content) {
    throw new AppError(400, "反馈内容不能为空。");
  }

  if (content.length > 2000) {
    throw new AppError(400, "反馈内容请控制在 2000 字以内。");
  }

  await d1Run(
    env.DB,
    "INSERT INTO site_feedback (feedback_type, content) VALUES (?, ?)",
    [feedbackType, content],
  );

  return { ok: true };
}

export async function voteComment(env: Env, commentId: number, payload: Record<string, unknown>) {
  if (!Number.isInteger(commentId) || commentId <= 0) {
    throw new AppError(400, "评论 ID 不合法。");
  }

  const voterId = String(payload.voterId || "").trim();
  const voteType = String(payload.voteType || "").trim().toLowerCase();

  if (!voterId || voterId.length > 128) {
    throw new AppError(400, "缺少有效的投票访客标识。");
  }

  if (voteType !== "up" && voteType !== "down") {
    throw new AppError(400, "投票类型必须是 up 或 down。");
  }

  const comment = await d1First<{ teacher_uid: string }>(
    env.DB,
    "SELECT teacher_uid FROM comments WHERE id = ?",
    [commentId],
  );
  if (!comment) {
    throw new AppError(404, `找不到评论: ${commentId}`);
  }

  const existingVote = await d1First<{ vote_type: string }>(
    env.DB,
    "SELECT vote_type FROM comment_votes WHERE comment_id = ? AND voter_id = ?",
    [commentId, voterId],
  );

  if (existingVote?.vote_type === voteType) {
    await d1Run(env.DB, "DELETE FROM comment_votes WHERE comment_id = ? AND voter_id = ?", [commentId, voterId]);
  } else if (existingVote) {
    await d1Run(
      env.DB,
      `
        UPDATE comment_votes
        SET vote_type = ?, updated_at = CURRENT_TIMESTAMP
        WHERE comment_id = ? AND voter_id = ?
      `,
      [voteType, commentId, voterId],
    );
  } else {
    await d1Run(
      env.DB,
      "INSERT INTO comment_votes (comment_id, voter_id, vote_type) VALUES (?, ?, ?)",
      [commentId, voterId, voteType],
    );
  }

  // 聚合字段保留在 comments 中，列表查询时不需要每次重新 COUNT。
  const totals = await d1First<Record<string, unknown>>(
    env.DB,
    `
      SELECT
        SUM(CASE WHEN vote_type = 'up' THEN 1 ELSE 0 END) AS upvotes,
        SUM(CASE WHEN vote_type = 'down' THEN 1 ELSE 0 END) AS downvotes
      FROM comment_votes
      WHERE comment_id = ?
    `,
    [commentId],
  );

  await d1Run(
    env.DB,
    "UPDATE comments SET upvotes = ?, downvotes = ? WHERE id = ?",
    [Number(totals?.upvotes || 0), Number(totals?.downvotes || 0), commentId],
  );

  return queryTeacherDetail(env, comment.teacher_uid);
}

export async function queryAdminSiteFeedback(env: Env) {
  const rows = await d1All<Record<string, unknown>>(
    env.DB,
    `
      SELECT id, feedback_type, content, created_at
      FROM site_feedback
      ORDER BY datetime(created_at) DESC, id DESC
      LIMIT 200
    `,
  );

  return {
    feedback: rows.map((row) => ({
      id: Number(row.id),
      feedbackType: String(row.feedback_type || "suggestion"),
      content: String(row.content || ""),
      date: String(row.created_at || ""),
    })),
  };
}

export async function deleteSiteFeedback(env: Env, feedbackId: number) {
  if (!Number.isInteger(feedbackId) || feedbackId <= 0) {
    throw new AppError(400, "反馈 ID 不合法。");
  }

  const row = await d1First<{ id: number }>(
    env.DB,
    "SELECT id FROM site_feedback WHERE id = ?",
    [feedbackId],
  );
  if (!row) {
    throw new AppError(404, `找不到反馈: ${feedbackId}`);
  }

  await d1Run(env.DB, "DELETE FROM site_feedback WHERE id = ?", [feedbackId]);
  return queryAdminSiteFeedback(env);
}

export async function queryAdminTeacherRankings(env: Env, sortBy = "reviews", keyword = "") {
  const teachers = await fetchTeacherRows(env);
  const reviewRows = await d1All<Record<string, unknown>>(
    env.DB,
    `
      SELECT
        teacher_uid,
        COUNT(*) AS review_count,
        SUM(CASE WHEN is_run_away = 1 THEN 1 ELSE 0 END) AS run_away_votes,
        AVG(score_ethics) AS avg_ethics,
        AVG(score_academic) AS avg_academic,
        AVG(score_wlb) AS avg_wlb,
        AVG(score_funding) AS avg_funding,
        AVG(score_graduation) AS avg_graduation,
        AVG(score_outcome) AS avg_outcome,
        MAX(created_at) AS last_reviewed_at
      FROM comments
      GROUP BY teacher_uid
    `,
  );
  const linkRows = await d1All<Record<string, unknown>>(
    env.DB,
    `
      SELECT teacher_uid, COUNT(*) AS link_count
      FROM cc98_links
      GROUP BY teacher_uid
    `,
  );

  const reviewStats = new Map(reviewRows.map((row) => [String(row.teacher_uid), row]));
  const linkStats = new Map(linkRows.map((row) => [String(row.teacher_uid), Number(row.link_count || 0)]));
  const keywordText = compactText(keyword);

  const rankingRows = teachers
    .filter((teacher) => {
      if (!keywordText) {
        return true;
      }

      const searchable = compactText(
        [
          teacher.name || "",
          teacher.workTitle || "",
          ...teacher.colleges.map((item: any) => item.collegeName),
        ].join(" "),
      );
      return searchable.includes(keywordText);
    })
    .map((teacher) => {
      const reviewRow = reviewStats.get(teacher.uid);
      const reviewCount = Number(reviewRow?.review_count || 0);
      const runAwayVotes = Number(reviewRow?.run_away_votes || 0);
      const averageScore = averageMetricValues([
        Number(reviewRow?.avg_ethics ?? NaN),
        Number(reviewRow?.avg_academic ?? NaN),
        Number(reviewRow?.avg_wlb ?? NaN),
        Number(reviewRow?.avg_funding ?? NaN),
        Number(reviewRow?.avg_graduation ?? NaN),
        Number(reviewRow?.avg_outcome ?? NaN),
      ].map((value) => (Number.isFinite(value) ? value : null)));

      return {
        uid: teacher.uid,
        name: teacher.name,
        workTitle: teacher.workTitle,
        colleges: teacher.colleges,
        reviewCount,
        runAwayVotes,
        averageScore,
        linkCount: linkStats.get(teacher.uid) || 0,
        lastReviewedAt: String(reviewRow?.last_reviewed_at || ""),
      };
    });

  if (sortBy === "score") {
    rankingRows.sort((left, right) => right.averageScore - left.averageScore || right.reviewCount - left.reviewCount);
  } else if (sortBy === "runaway") {
    rankingRows.sort((left, right) => right.runAwayVotes - left.runAwayVotes || right.reviewCount - left.reviewCount);
  } else if (sortBy === "links") {
    rankingRows.sort((left, right) => right.linkCount - left.linkCount || right.reviewCount - left.reviewCount);
  } else {
    sortBy = "reviews";
    rankingRows.sort((left, right) => right.reviewCount - left.reviewCount || right.averageScore - left.averageScore);
  }

  return {
    sortBy,
    query: keyword,
    teachers: rankingRows,
  };
}

export async function deleteCommentRecord(env: Env, commentId: number) {
  const row = await d1First<{ teacher_uid: string }>(
    env.DB,
    "SELECT teacher_uid FROM comments WHERE id = ?",
    [commentId],
  );
  if (!row) {
    throw new AppError(404, `找不到评论: ${commentId}`);
  }

  await d1Run(env.DB, "DELETE FROM comment_votes WHERE comment_id = ?", [commentId]);
  await d1Run(env.DB, "DELETE FROM comments WHERE id = ?", [commentId]);
  return queryTeacherDetail(env, row.teacher_uid);
}

export async function deleteLinkRecord(env: Env, linkId: number) {
  const row = await d1First<{ teacher_uid: string }>(
    env.DB,
    "SELECT teacher_uid FROM cc98_links WHERE id = ?",
    [linkId],
  );
  if (!row) {
    throw new AppError(404, `找不到链接: ${linkId}`);
  }

  await d1Run(env.DB, "DELETE FROM cc98_links WHERE id = ?", [linkId]);
  return queryTeacherDetail(env, row.teacher_uid);
}
