import fs from "node:fs";
import path from "node:path";

type CollegeSnapshot = {
  college_id: string;
  college_name: string;
  big_unit_id?: string | null;
  big_unit_name?: string | null;
};

type TeacherSnapshot = {
  uid: string;
  name: string;
  work_title: string;
  department: string;
  mapping_name: string | null;
  profile_url: string;
  departments: Array<{ college_id: string; college_name: string }>;
};

const root = path.resolve(process.cwd(), "..");
const dataDir = path.join(root, "data");
const outputDir = path.join(process.cwd(), "tmp");

const collegesPath = path.join(dataDir, "zju_colleges.json");
const teachersPath = path.join(dataDir, "all_zju_teachers.json");
const schemaPath = path.join(process.cwd(), "migrations", "0001_init.sql");
const outputPath = path.join(outputDir, "seed.sql");

function escapeSql(value: string | null | undefined): string {
  if (value === null || value === undefined) {
    return "NULL";
  }

  return `'${String(value).replaceAll("'", "''")}'`;
}

function main() {
  const colleges = JSON.parse(fs.readFileSync(collegesPath, "utf8")) as CollegeSnapshot[];
  const teachers = JSON.parse(fs.readFileSync(teachersPath, "utf8")) as TeacherSnapshot[];

  fs.mkdirSync(outputDir, { recursive: true });

  const lines: string[] = [];
  lines.push(fs.readFileSync(schemaPath, "utf8").trim());

  const seenBigUnits = new Set<string>();
  for (const college of colleges) {
    if (college.big_unit_id && college.big_unit_name && !seenBigUnits.has(college.big_unit_id)) {
      seenBigUnits.add(college.big_unit_id);
      lines.push(
        `INSERT OR IGNORE INTO big_departments (id, name) VALUES (${escapeSql(college.big_unit_id)}, ${escapeSql(college.big_unit_name)});`,
      );
    }

    lines.push(
      `INSERT OR REPLACE INTO departments (college_id, college_name, big_dept_id) VALUES (${escapeSql(college.college_id)}, ${escapeSql(college.college_name)}, ${escapeSql(college.big_unit_id || null)});`,
    );
  }

  const seenHiddenDepartments = new Set<string>();
  for (const teacher of teachers) {
    lines.push(
      `INSERT OR REPLACE INTO teachers (uid, name, work_title, department, mapping_name, profile_url) VALUES (${escapeSql(teacher.uid)}, ${escapeSql(teacher.name)}, ${escapeSql(teacher.work_title)}, ${escapeSql(teacher.department)}, ${escapeSql(teacher.mapping_name)}, ${escapeSql(teacher.profile_url)});`,
    );

    for (const department of teacher.departments || []) {
      if (!seenHiddenDepartments.has(department.college_id)) {
        seenHiddenDepartments.add(department.college_id);
        lines.push(
          `INSERT OR IGNORE INTO departments (college_id, college_name, big_dept_id) VALUES (${escapeSql(department.college_id)}, ${escapeSql(department.college_name)}, NULL);`,
        );
      }

      lines.push(
        `INSERT OR IGNORE INTO teacher_department_relations (teacher_uid, college_id) VALUES (${escapeSql(teacher.uid)}, ${escapeSql(department.college_id)});`,
      );
    }
  }

  fs.writeFileSync(outputPath, `${lines.join("\n")}\n`, "utf8");
  console.log(`seed SQL written to ${outputPath}`);
}

main();
