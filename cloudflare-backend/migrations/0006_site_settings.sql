CREATE TABLE IF NOT EXISTS site_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO site_settings (key, value) VALUES ('show_portal_stats', 'false');
INSERT OR IGNORE INTO site_settings (key, value) VALUES ('show_discussion_group', 'false');
INSERT OR IGNORE INTO site_settings (key, value) VALUES ('author_contact_mode', 'form');
