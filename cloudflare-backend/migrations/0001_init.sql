CREATE TABLE IF NOT EXISTS big_departments (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS departments (
  college_id TEXT PRIMARY KEY,
  college_name TEXT NOT NULL,
  big_dept_id TEXT,
  FOREIGN KEY (big_dept_id) REFERENCES big_departments (id)
);

CREATE TABLE IF NOT EXISTS teachers (
  uid TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  work_title TEXT,
  department TEXT,
  mapping_name TEXT,
  profile_url TEXT
);

CREATE TABLE IF NOT EXISTS teacher_department_relations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  teacher_uid TEXT NOT NULL,
  college_id TEXT NOT NULL,
  FOREIGN KEY (teacher_uid) REFERENCES teachers (uid),
  FOREIGN KEY (college_id) REFERENCES departments (college_id),
  UNIQUE (teacher_uid, college_id)
);

CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  teacher_uid TEXT NOT NULL,
  identity TEXT NOT NULL DEFAULT '',
  content TEXT,
  score_ethics REAL CHECK(score_ethics BETWEEN 0 AND 5),
  score_academic REAL CHECK(score_academic BETWEEN 0 AND 5),
  score_wlb REAL CHECK(score_wlb BETWEEN 0 AND 5),
  score_funding REAL CHECK(score_funding BETWEEN 0 AND 5),
  score_graduation REAL CHECK(score_graduation BETWEEN 0 AND 5),
  score_outcome REAL CHECK(score_outcome BETWEEN 0 AND 5),
  is_run_away INTEGER NOT NULL DEFAULT 0,
  upvotes INTEGER DEFAULT 0,
  downvotes INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (teacher_uid) REFERENCES teachers (uid)
);

CREATE TABLE IF NOT EXISTS comment_votes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  comment_id INTEGER NOT NULL,
  voter_id TEXT NOT NULL,
  vote_type TEXT NOT NULL CHECK (vote_type IN ('up', 'down')),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (comment_id) REFERENCES comments (id),
  UNIQUE (comment_id, voter_id)
);

CREATE TABLE IF NOT EXISTS cc98_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  teacher_uid TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT,
  link_type TEXT NOT NULL DEFAULT 'cc98',
  description TEXT NOT NULL DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (teacher_uid) REFERENCES teachers (uid)
);

CREATE TABLE IF NOT EXISTS site_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  feedback_type TEXT NOT NULL CHECK (feedback_type IN ('error', 'suggestion')),
  content TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_visits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  visit_date TEXT NOT NULL,
  visitor_id TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (visit_date, visitor_id)
);

CREATE TABLE IF NOT EXISTS sync_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  summary_json TEXT NOT NULL DEFAULT '{}',
  error_message TEXT NOT NULL DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  finished_at DATETIME
);

CREATE TABLE IF NOT EXISTS site_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO site_settings (key, value) VALUES ('show_portal_stats', 'false');
INSERT OR IGNORE INTO site_settings (key, value) VALUES ('show_discussion_group', 'false');
INSERT OR IGNORE INTO site_settings (key, value) VALUES ('author_contact_mode', 'form');
INSERT OR IGNORE INTO site_settings (key, value) VALUES ('show_about_links', 'false');
INSERT OR IGNORE INTO site_settings (key, value) VALUES ('show_data_download', 'false');

CREATE INDEX IF NOT EXISTS idx_departments_big_dept_id ON departments (big_dept_id);
CREATE INDEX IF NOT EXISTS idx_rel_teacher_uid ON teacher_department_relations (teacher_uid);
CREATE INDEX IF NOT EXISTS idx_rel_college_id ON teacher_department_relations (college_id);
CREATE INDEX IF NOT EXISTS idx_comments_teacher_uid ON comments (teacher_uid);
CREATE INDEX IF NOT EXISTS idx_comments_created_at ON comments (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comment_votes_comment_id ON comment_votes (comment_id);
CREATE INDEX IF NOT EXISTS idx_comment_votes_voter_id ON comment_votes (voter_id);
CREATE INDEX IF NOT EXISTS idx_links_teacher_uid ON cc98_links (teacher_uid);
CREATE INDEX IF NOT EXISTS idx_links_created_at ON cc98_links (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_site_feedback_created_at ON site_feedback (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_site_feedback_type ON site_feedback (feedback_type);
CREATE INDEX IF NOT EXISTS idx_daily_visits_visit_date ON daily_visits (visit_date);
CREATE INDEX IF NOT EXISTS idx_sync_runs_created_at ON sync_runs (created_at DESC);
