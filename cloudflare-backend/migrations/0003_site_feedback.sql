-- 站点反馈表：用于收集导师信息错误、网站 bug、反馈与建议。
CREATE TABLE IF NOT EXISTS site_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  feedback_type TEXT NOT NULL CHECK (feedback_type IN ('error', 'suggestion')),
  content TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_site_feedback_created_at ON site_feedback (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_site_feedback_type ON site_feedback (feedback_type);
