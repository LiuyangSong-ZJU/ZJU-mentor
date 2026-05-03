import { launch } from "@cloudflare/playwright";
import { d1All, d1First, d1Run } from "../db/queries";
import type { CollegeSnapshot, Env, SyncStats, TeacherSnapshot } from "../types";
import { AppError } from "../utils/response";

const EXCLUDE_LIST = [
  "学院（系）",
  "其他单位",
  "人文学部",
  "社会科学学部",
  "理学部",
  "工学部",
  "信息学部",
  "农业生命环境学部",
  "医药学部",
  "国际校区",
];

const BIG_UNITS = [
  "人文学部",
  "社会科学学部",
  "理学部",
  "工学部",
  "信息学部",
  "农业生命环境学部",
  "医药学部",
  "国际校区",
  "其他单位",
];

function parseCollegesTree(
  collegeList: any[],
  resultList: CollegeSnapshot[],
  currentBigUnitId: string | null = null,
  currentBigUnitName: string | null = null,
) {
  for (const item of collegeList || []) {
    const collegeId = item?.collegeId;
    const collegeName = item?.collegeName;

    let nextBigId = currentBigUnitId;
    let nextBigName = currentBigUnitName;

    if (BIG_UNITS.includes(collegeName)) {
      nextBigId = collegeId;
      nextBigName = collegeName;
    }

    if (collegeId && collegeName && !EXCLUDE_LIST.includes(collegeName)) {
      resultList.push({
        college_id: String(collegeId),
        college_name: String(collegeName),
        level: Number(item?.level || 0),
        big_unit_id: nextBigId,
        big_unit_name: nextBigName,
      });
    }

    if (Array.isArray(item?.collegeList) && item.collegeList.length > 0) {
      parseCollegesTree(item.collegeList, resultList, nextBigId, nextBigName);
    }
  }
}

function processTeacherApiData(
  data: any,
  currentPageId: string,
  currentPageName: string,
  allTeachers: Map<string, any>,
) {
  const contentList = data?.data?.content || [];

  for (const item of contentList) {
    const uid = item?.uid;
    if (!uid) {
      continue;
    }

    const name = item?.cn_name || "未知";
    const workTitle = item?.work_title_name || "无职称";
    const mappingName = item?.mapping_name || null;
    const rawCollegeName = String(item?.college_name || "未知单位");
    const rawCollegeId = String(item?.college_id || "未知ID");

    const collegeIds = rawCollegeId.split(",");
    const collegeNames = rawCollegeName.replaceAll("|", ",").split(",");
    const urlSuffix = mappingName || uid;
    const profileUrl = `https://person.zju.edu.cn/${urlSuffix}`;

    if (!allTeachers.has(uid)) {
      allTeachers.set(uid, {
        uid,
        name,
        work_title: workTitle,
        department: rawCollegeName,
        mapping_name: mappingName,
        profile_url: profileUrl,
        departments_map: new Map<string, string>(),
      });
    } else {
      const existing = allTeachers.get(uid);
      if (rawCollegeName.length > String(existing.department || "").length) {
        existing.department = rawCollegeName;
      }
      existing.name = name;
      existing.work_title = workTitle;
      existing.mapping_name = mappingName;
      existing.profile_url = profileUrl;
    }

    const teacher = allTeachers.get(uid);
    for (let index = 0; index < collegeIds.length; index += 1) {
      const collegeId = collegeIds[index]?.trim();
      const collegeName = (collegeNames[index] || collegeNames[0] || "").trim();
      if (collegeId) {
        teacher.departments_map.set(collegeId, collegeName);
      }
    }

    teacher.departments_map.set(currentPageId, currentPageName);
  }
}

function normalizeTeacherDepartments(
  teachersMap: Map<string, any>,
  officialColleges: CollegeSnapshot[],
): TeacherSnapshot[] {
  const officialIdToName = new Map(officialColleges.map((item) => [item.college_id, item.college_name]));
  const officialNameToId = new Map(officialColleges.map((item) => [item.college_name, item.college_id]));
  const finalTeachers: TeacherSnapshot[] = [];

  for (const teacher of teachersMap.values()) {
    const correctedDepartments = new Map<string, string>();

    for (const [collegeId, collegeName] of teacher.departments_map.entries()) {
      if (officialNameToId.has(collegeName) && collegeId !== officialNameToId.get(collegeName)) {
        correctedDepartments.set(String(officialNameToId.get(collegeName)), collegeName);
      } else {
        correctedDepartments.set(collegeId, collegeName);
      }
    }

    const departments = [...correctedDepartments.entries()].map(([collegeId, collegeName]) => ({
      college_id: collegeId,
      college_name: collegeName,
    }));

    finalTeachers.push({
      uid: teacher.uid,
      name: teacher.name,
      work_title: teacher.work_title,
      department: teacher.department,
      mapping_name: teacher.mapping_name,
      profile_url: teacher.profile_url,
      departments,
    });

    for (const department of departments) {
      if (!officialIdToName.has(department.college_id)) {
        void department;
      }
    }
  }

  return finalTeachers;
}

async function requireBrowserBinding(env: Env) {
  if (!env.MYBROWSER) {
    throw new AppError(501, "当前环境未绑定 Browser Run，无法执行云端抓取。");
  }

  return launch(env.MYBROWSER as never);
}

export async function fetchLatestColleges(env: Env): Promise<CollegeSnapshot[]> {
  const baseUrl = env.ZJU_BASE_URL || "https://person.zju.edu.cn";
  const browser = await requireBrowserBinding(env);
  const page = await browser.newPage();

  try {
    const responsePromise = page.waitForResponse(
      (response) => response.url().includes("api/front/colleges"),
      { timeout: 30000 },
    );
    await page.goto(`${baseUrl}/index/childPages/unit`, { waitUntil: "domcontentloaded", timeout: 60000 });
    const response = await responsePromise;
    const payload = await response.json();
    if (payload?.code !== 200) {
      throw new AppError(502, `单位接口返回异常 code: ${String(payload?.code)}`);
    }

    const results: CollegeSnapshot[] = [];
    parseCollegesTree(payload?.data || [], results);
    return results;
  } finally {
    await page.close();
    await browser.close();
  }
}

export async function fetchLatestTeachers(env: Env, colleges: CollegeSnapshot[]): Promise<TeacherSnapshot[]> {
  const baseUrl = env.ZJU_BASE_URL || "https://person.zju.edu.cn";
  const allTeachers = new Map<string, any>();
  const browser = await requireBrowserBinding(env);
  const page = await browser.newPage();

  try {
    for (const [index, college] of colleges.entries()) {
      console.log(`[${String(index + 1).padStart(2, "0")}/${colleges.length}] 抓取导师: ${college.college_name}`);

      try {
        const firstResponsePromise = page.waitForResponse(
          (response) => response.url().includes("api/front/psons/search") && response.status() === 200,
          { timeout: 30000 },
        );
        await page.goto(`${baseUrl}/index/search?companys=${encodeURIComponent(college.college_id)}`, {
          waitUntil: "domcontentloaded",
          timeout: 60000,
        });
        const firstResponse = await firstResponsePromise;
        const firstPayload = await firstResponse.json();

        if (firstPayload?.code !== 200) {
          console.log(`  -> 跳过，接口 code 异常: ${String(firstPayload?.code)}`);
          continue;
        }

        const totalPages = Number(firstPayload?.data?.totalPages || 0);
        processTeacherApiData(firstPayload, college.college_id, college.college_name, allTeachers);

        let fetchedPages = 1;
        while (fetchedPages < totalPages) {
          await page.evaluate("window.scrollTo(0, document.body.scrollHeight)");
          await page.waitForTimeout(800);

          const moreButtons = page.locator("text=查看更多");
          if ((await moreButtons.count()) === 0 || !(await moreButtons.last().isVisible())) {
            console.log(`  -> 提前结束翻页，已抓到 ${fetchedPages}/${totalPages} 页`);
            break;
          }

          const nextResponsePromise = page.waitForResponse(
            (response) => response.url().includes("api/front/psons/search") && response.status() === 200,
            { timeout: 15000 },
          );

          await moreButtons.last().click({ force: true });
          const nextPayload = await (await nextResponsePromise).json();
          processTeacherApiData(nextPayload, college.college_id, college.college_name, allTeachers);
          fetchedPages += 1;
        }
      } catch (error) {
        console.log(`  -> 抓取失败，跳过该单位: ${String(error)}`);
      }
    }
  } finally {
    await page.close();
    await browser.close();
  }

  return normalizeTeacherDepartments(allTeachers, colleges);
}

async function syncBigDepartments(env: Env, colleges: CollegeSnapshot[]) {
  const stats = { inserted: 0, updated: 0 };
  const existingRows = await d1All<{ id: string; name: string }>(env.DB, "SELECT id, name FROM big_departments");
  const existing = new Map(existingRows.map((row) => [row.id, row.name]));
  const seen = new Set<string>();

  for (const item of colleges) {
    const bigId = item.big_unit_id;
    const bigName = item.big_unit_name;
    if (!bigId || !bigName || seen.has(bigId)) {
      continue;
    }

    seen.add(bigId);
    if (!existing.has(bigId)) {
      await d1Run(env.DB, "INSERT INTO big_departments (id, name) VALUES (?, ?)", [bigId, bigName]);
      stats.inserted += 1;
    } else if (existing.get(bigId) !== bigName) {
      await d1Run(env.DB, "UPDATE big_departments SET name = ? WHERE id = ?", [bigName, bigId]);
      stats.updated += 1;
    }
  }

  return stats;
}

async function syncDepartments(env: Env, colleges: CollegeSnapshot[], teachers: TeacherSnapshot[]) {
  const stats = { inserted: 0, updated: 0, inserted_names: [] as string[] };
  const existingRows = await d1All<{ college_id: string; college_name: string; big_dept_id: string | null }>(
    env.DB,
    "SELECT college_id, college_name, big_dept_id FROM departments",
  );

  const existing = new Map(existingRows.map((row) => [row.college_id, row]));
  const desired = new Map<string, { college_name: string; big_dept_id: string | null }>();

  for (const item of colleges) {
    desired.set(item.college_id, {
      college_name: item.college_name,
      big_dept_id: item.big_unit_id || null,
    });
  }

  for (const teacher of teachers) {
    for (const department of teacher.departments) {
      if (!desired.has(department.college_id)) {
        desired.set(department.college_id, {
          college_name: department.college_name,
          big_dept_id: null,
        });
      }
    }
  }

  for (const [collegeId, target] of desired.entries()) {
    const current = existing.get(collegeId);
    if (!current) {
      await d1Run(
        env.DB,
        "INSERT INTO departments (college_id, college_name, big_dept_id) VALUES (?, ?, ?)",
        [collegeId, target.college_name, target.big_dept_id],
      );
      stats.inserted += 1;
      stats.inserted_names.push(target.college_name);
      continue;
    }

    if (current.college_name !== target.college_name || current.big_dept_id !== target.big_dept_id) {
      await d1Run(
        env.DB,
        "UPDATE departments SET college_name = ?, big_dept_id = ? WHERE college_id = ?",
        [target.college_name, target.big_dept_id, collegeId],
      );
      stats.updated += 1;
    }
  }

  return stats;
}

async function syncTeachers(env: Env, teachers: TeacherSnapshot[]) {
  const stats = { inserted: 0, updated: 0, inserted_names: [] as string[] };
  const existingRows = await d1All<{
    uid: string;
    name: string;
    work_title: string | null;
    department: string | null;
    mapping_name: string | null;
    profile_url: string | null;
  }>(
    env.DB,
    "SELECT uid, name, work_title, department, mapping_name, profile_url FROM teachers",
  );
  const existing = new Map(existingRows.map((row) => [row.uid, row]));

  for (const teacher of teachers) {
    const current = existing.get(teacher.uid);
    if (!current) {
      await d1Run(
        env.DB,
        `
          INSERT INTO teachers (uid, name, work_title, department, mapping_name, profile_url)
          VALUES (?, ?, ?, ?, ?, ?)
        `,
        [
          teacher.uid,
          teacher.name,
          teacher.work_title,
          teacher.department,
          teacher.mapping_name,
          teacher.profile_url,
        ],
      );
      stats.inserted += 1;
      stats.inserted_names.push(teacher.name);
      continue;
    }

    if (
      current.name !== teacher.name ||
      current.work_title !== teacher.work_title ||
      current.department !== teacher.department ||
      current.mapping_name !== teacher.mapping_name ||
      current.profile_url !== teacher.profile_url
    ) {
      await d1Run(
        env.DB,
        `
          UPDATE teachers
          SET name = ?, work_title = ?, department = ?, mapping_name = ?, profile_url = ?
          WHERE uid = ?
        `,
        [
          teacher.name,
          teacher.work_title,
          teacher.department,
          teacher.mapping_name,
          teacher.profile_url,
          teacher.uid,
        ],
      );
      stats.updated += 1;
    }
  }

  return stats;
}

async function syncTeacherDepartmentRelations(env: Env, teachers: TeacherSnapshot[]) {
  const stats = { inserted: 0, deleted: 0 };
  const rows = await d1All<{ teacher_uid: string; college_id: string }>(
    env.DB,
    "SELECT teacher_uid, college_id FROM teacher_department_relations",
  );
  const existing = new Map<string, Set<string>>();
  for (const row of rows) {
    const current = existing.get(row.teacher_uid) || new Set<string>();
    current.add(row.college_id);
    existing.set(row.teacher_uid, current);
  }

  for (const teacher of teachers) {
    const latestRelations = new Set(teacher.departments.map((department) => department.college_id));
    const currentRelations = existing.get(teacher.uid) || new Set<string>();

    for (const collegeId of latestRelations) {
      if (!currentRelations.has(collegeId)) {
        await d1Run(
          env.DB,
          "INSERT OR IGNORE INTO teacher_department_relations (teacher_uid, college_id) VALUES (?, ?)",
          [teacher.uid, collegeId],
        );
        stats.inserted += 1;
      }
    }

    for (const collegeId of currentRelations) {
      if (!latestRelations.has(collegeId)) {
        await d1Run(
          env.DB,
          "DELETE FROM teacher_department_relations WHERE teacher_uid = ? AND college_id = ?",
          [teacher.uid, collegeId],
        );
        stats.deleted += 1;
      }
    }
  }

  return stats;
}

export async function syncSnapshots(
  env: Env,
  colleges: CollegeSnapshot[],
  teachers: TeacherSnapshot[],
): Promise<SyncStats> {
  const bigStats = await syncBigDepartments(env, colleges);
  const departmentStats = await syncDepartments(env, colleges, teachers);
  const teacherStats = await syncTeachers(env, teachers);
  const relationStats = await syncTeacherDepartmentRelations(env, teachers);

  return {
    big_departments: bigStats,
    departments: departmentStats,
    teachers: teacherStats,
    relations: relationStats,
  };
}

async function createSyncRun(env: Env, mode: string): Promise<number> {
  await d1Run(
    env.DB,
    `
      UPDATE sync_runs
      SET status = 'failed',
          error_message = 'Interrupted before completion; superseded by a later sync run.',
          finished_at = CURRENT_TIMESTAMP
      WHERE status = 'running'
    `,
  );

  await d1Run(
    env.DB,
    "INSERT INTO sync_runs (mode, status, summary_json, error_message) VALUES (?, 'running', '{}', '')",
    [mode],
  );

  const row = await d1First<{ id: number }>(env.DB, "SELECT id FROM sync_runs ORDER BY id DESC LIMIT 1");
  return Number(row?.id || 0);
}

async function finishSyncRun(env: Env, id: number, status: "success" | "failed", payload: unknown, errorMessage = "") {
  await d1Run(
    env.DB,
    `
      UPDATE sync_runs
      SET status = ?, summary_json = ?, error_message = ?, finished_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `,
    [status, JSON.stringify(payload), errorMessage, id],
  );
}

export async function listSyncRuns(env: Env) {
  const totalRow = await d1First<Record<string, unknown>>(
    env.DB,
    "SELECT COUNT(*) AS total FROM sync_runs",
  );
  const runs = await d1All<Record<string, unknown>>(
    env.DB,
    `
      SELECT id, mode, status, summary_json, error_message, created_at, finished_at
      FROM sync_runs
      ORDER BY id DESC
      LIMIT 20
    `,
  );

  return {
    total: Number(totalRow?.total || 0),
    runs,
  };
}

export async function runFullSync(env: Env, mode = "crawler") {
  const runId = await createSyncRun(env, mode);

  try {
    const colleges = await fetchLatestColleges(env);
    const teachers = await fetchLatestTeachers(env, colleges);
    const stats = await syncSnapshots(env, colleges, teachers);
    const payload = {
      stats,
      colleges: colleges.length,
      teachers: teachers.length,
    };

    await finishSyncRun(env, runId, "success", payload);
    return payload;
  } catch (error) {
    await finishSyncRun(env, runId, "failed", {}, String(error));
    throw error;
  }
}

export async function runScheduledSync(env: Env) {
  if ((env.SYNC_ENABLED || "true").toLowerCase() === "false") {
    return { skipped: true, reason: "SYNC_ENABLED=false" };
  }

  return runFullSync(env, "scheduled-crawler");
}
