export interface Env {
  DB: D1Database;
  ADMIN_TOKEN?: string;
  SYNC_ENABLED?: string;
  ZJU_BASE_URL?: string;
  MYBROWSER?: unknown;
  ASSETS?: Fetcher;
}

export interface CollegeSnapshot {
  college_id: string;
  college_name: string;
  level?: number | null;
  big_unit_id?: string | null;
  big_unit_name?: string | null;
}

export interface TeacherDepartmentSnapshot {
  college_id: string;
  college_name: string;
}

export interface TeacherSnapshot {
  uid: string;
  name: string;
  work_title: string;
  department: string;
  mapping_name: string | null;
  profile_url: string;
  departments: TeacherDepartmentSnapshot[];
}

export interface SyncStats {
  big_departments: { inserted: number; updated: number };
  departments: { inserted: number; updated: number; inserted_names: string[] };
  teachers: { inserted: number; updated: number; inserted_names: string[] };
  relations: { inserted: number; deleted: number };
}

export interface AppErrorLike extends Error {
  status?: number;
}
