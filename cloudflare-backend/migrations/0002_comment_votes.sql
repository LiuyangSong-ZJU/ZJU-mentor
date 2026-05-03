-- 为评论点赞/点踩增加明细表：一位匿名访客对同一条评论只能保留一个当前投票。
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

CREATE INDEX IF NOT EXISTS idx_comment_votes_comment_id ON comment_votes (comment_id);
CREATE INDEX IF NOT EXISTS idx_comment_votes_voter_id ON comment_votes (voter_id);
