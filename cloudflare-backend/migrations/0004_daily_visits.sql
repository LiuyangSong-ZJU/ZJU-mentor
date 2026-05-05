-- 今日访问人数统计：按日期和匿名访客标识去重。
CREATE TABLE IF NOT EXISTS daily_visits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  visit_date TEXT NOT NULL,
  visitor_id TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (visit_date, visitor_id)
);

CREATE INDEX IF NOT EXISTS idx_daily_visits_visit_date ON daily_visits (visit_date);
