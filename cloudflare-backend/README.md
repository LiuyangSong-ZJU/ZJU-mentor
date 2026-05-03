# ZJU Mentor Cloudflare Backend

这是当前项目的 Cloudflare 原生后端版本，目标是替代根目录里的 Python 本地后端：

- `Workers` 提供同源网页与 `/api/*`
- `D1` 保存导师、单位、评论、链接和同步记录
- `Browser Run` 执行增量式爬虫
- `Cron Triggers` 定时触发数据库更新

## 本地启动

安装依赖：

```bash
cd /Users/pipi/Life/ZJU-mentor/cloudflare-backend
npm install
```

创建 D1 数据库后，确认 [wrangler.jsonc](/Users/pipi/Life/ZJU-mentor/cloudflare-backend/wrangler.jsonc:1) 里只有一个 `DB` binding，并且 `database_id` 是 Cloudflare 返回的真实 id：

```bash
npx wrangler d1 create zju-mentor-db
```

用当前仓库的 JSON 初始化本地 D1：

```bash
npm run d1:seed:local
```

启动网页和 API：

```bash
npx wrangler dev --ip 127.0.0.1 --port 8787
```

本地访问地址：

```text
http://127.0.0.1:8787
```

本地后台口令在 `.dev.vars`：

```text
local-dev-admin-token
```

`.dev.vars` 已被根目录 `.gitignore` 忽略，不应提交。

## JSON 建库

当前 JSON 建库入口是：

```bash
npm run seed:sql
```

它读取：

- `/Users/pipi/Life/ZJU-mentor/data/zju_colleges.json`
- `/Users/pipi/Life/ZJU-mentor/data/all_zju_teachers.json`
- `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/migrations/0001_init.sql`

它生成：

- `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/tmp/seed.sql`

`tmp/seed.sql` 里面包含完整建表 SQL 和初始化数据 SQL，所以本地第一次建库时可以直接执行它，不需要先单独跑 migration。

执行到本地 D1：

```bash
npm run d1:seed:local
```

执行到远程 D1：

```bash
npm run d1:seed:remote
```

## 增量式更新

本地手动触发增量更新：

```bash
curl -s -X POST http://127.0.0.1:8787/api/admin/sync/run \
  -H 'X-Admin-Token: local-dev-admin-token'
```

查看最近 20 次同步记录：

```bash
curl -s http://127.0.0.1:8787/api/admin/sync/runs \
  -H 'X-Admin-Token: local-dev-admin-token'
```

线上手动触发时，把域名和 token 换成生产环境值：

```bash
curl -s -X POST https://your-domain.example.com/api/admin/sync/run \
  -H 'X-Admin-Token: your-production-admin-token'
```

定时更新配置在 [wrangler.jsonc](/Users/pipi/Life/ZJU-mentor/cloudflare-backend/wrangler.jsonc:1)：

```json
"triggers": {
  "crons": ["0 19 * * *"]
}
```

现在定时同步推荐交给 GitHub Actions：先导出 D1 备份并发布公开数据包，再触发线上增量同步。Worker 自己的 Cron 已从 `wrangler.jsonc` 移除，避免绕过备份直接写库。

手动触发线上同步时，建议不要直接 `curl /api/admin/sync/run`，而是使用“先备份再同步”的脚本：

```bash
cd /Users/pipi/Life/ZJU-mentor/cloudflare-backend
ZJU_MENTOR_SYNC_URL=https://your-domain.example.com \
ZJU_MENTOR_ADMIN_TOKEN=your-production-admin-token \
npm run sync:remote:with-backup
```

增量更新规则迁移自 `/Users/pipi/Life/ZJU-mentor/incremental_update_db.py`：

- 大单位只新增或更新，不删除
- 小单位只新增或更新，不删除
- 老师按 `uid` 新增或更新，不删除
- 出现在最新抓取结果里的老师，其单位关系以最新抓取结果为准
- 没出现在最新抓取结果里的旧老师，其旧单位关系保留
- 评论和链接不会被爬虫覆盖
- 每次同步写入 `sync_runs` 表，记录状态、摘要和错误信息

## 数据备份与公开数据包

生成本地 D1 备份：

```bash
cd /Users/pipi/Life/ZJU-mentor/cloudflare-backend
npm run backup:local
```

生成远程 D1 备份：

```bash
cd /Users/pipi/Life/ZJU-mentor/cloudflare-backend
npm run backup:remote
```

备份目录：

- `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/backups/YYYY-MM-DDTHH-MM-SSZ`

每个备份目录包含：

- `database-full.sql.gz`
  - 完整恢复包，包含所有表，可用于灾难恢复
- `database-public.sql.gz`
  - 公开数据包，只包含老师、单位、评论、链接等公开表
- `json/full/*.json`
  - 完整表 JSON，包含 `site_feedback`、`sync_runs`、`comment_votes`
- `json/public/*.json`
  - 公开表 JSON，不包含反馈内容、同步日志和匿名投票标识
- `manifest.json`
  - 生成时间、表列表、行数、sha256

保留策略由 `scripts/create-data-backup.mjs` 自动执行：

- 一周内：全部保留
- 超过一周但不到两个月：每 7 天保留一份，其余删除
- 超过两个月：每个月保留一份，其余删除

GitHub Actions 工作流在 `.github/workflows/backup-and-sync.yml`：

1. 每天北京时间 02:50 或手动触发。
2. 生成远程 D1 备份。
3. 把公开包发布到 GitHub Release。
4. 再调用线上 `/api/admin/sync/run` 执行增量抓取和同步。

需要在 GitHub 仓库 `Settings -> Secrets and variables -> Actions -> Repository secrets` 设置：

- `CLOUDFLARE_API_TOKEN`
  - 需要 D1 读取/导出权限
- `CLOUDFLARE_ACCOUNT_ID`
  - Cloudflare 账号 ID
- `ZJU_MENTOR_SYNC_URL`
  - 线上站点地址，例如 `https://your-domain.example.com`
- `ZJU_MENTOR_ADMIN_TOKEN`
  - 线上后台口令

## 文件位置

依赖目录：

- `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/node_modules`
  - Cloudflare 后端依赖，由 `npm install` 生成，已忽略
- `/Users/pipi/Life/ZJU-mentor/zju-mentor-frontend/node_modules`
  - Vue 前端依赖，已忽略

输入 JSON：

- `/Users/pipi/Life/ZJU-mentor/data/zju_colleges.json`
  - 当前 canonical 单位快照
  - `seed-from-json.ts` 会用它生成大单位和小单位初始数据
- `/Users/pipi/Life/ZJU-mentor/data/all_zju_teachers.json`
  - 当前 canonical 导师快照
  - `seed-from-json.ts` 会用它生成导师和导师-单位关系初始数据

生成 JSON：

- 当前 Cloudflare 后端不会默认落盘最新爬虫 JSON
  - 增量爬虫直接抓取并写入 D1
  - 如果后续需要保留快照，可以再接 R2/KV 或新增导出脚本
- Python 旧脚本仍可能生成 `/Users/pipi/Life/ZJU-mentor/data/latest_zju_colleges.json`
  - 根目录 `.gitignore` 已忽略 `data/latest_*.json`
- Python 旧脚本仍可能生成 `/Users/pipi/Life/ZJU-mentor/data/latest_all_zju_teachers.json`
  - 仅旧流程使用，Cloudflare 版不依赖它

D1 和 SQLite 文件：

- `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/.wrangler/state/v3/d1`
  - Wrangler 本地 D1 存储目录
  - 里面的 `.sqlite` 文件就是本地 D1 数据库
  - 已忽略，不提交
- `/Users/pipi/Life/ZJU-mentor/zju_teachers.db`
  - 旧 Python 后端使用的本地 SQLite
  - Cloudflare 后端不直接读取它
  - 后续如果要迁移历史评论和链接，需要单独导出再导入 D1

生成 SQL：

- `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/tmp/seed.sql`
  - 由 `npm run seed:sql` 生成
  - 包含 schema 和 JSON 初始化数据
  - 可重复生成，已忽略

前端构建产物：

- `/Users/pipi/Life/ZJU-mentor/zju-mentor-frontend/dist`
  - 由 `npm run build` 在前端目录生成
  - Worker Assets 会从这里托管网页
  - 已忽略

本地配置和日志：

- `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/.dev.vars`
  - 本地 Worker 环境变量，例如 `ADMIN_TOKEN`
  - 已忽略，不提交
- `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/.wrangler`
  - Wrangler 本地状态、缓存、本地 D1
  - 已忽略
- `/Users/pipi/Library/Preferences/.wrangler/logs`
  - Wrangler 自己的运行日志目录
  - 不属于项目目录

## 主要接口

公开接口：

- `GET /api/units`
- `GET /api/teachers/by-name`
- `GET /api/teachers/suggest?q=zs`
- `GET /api/teachers/search?q=zhang`
- `GET /api/units/:collegeId/teachers`
- `GET /api/teachers/:uid`
- `POST /api/teachers/:uid/comments`
- `POST /api/teachers/:uid/links`

后台接口：

- `POST /api/admin/session`
- `GET /api/admin/teachers`
- `GET /api/admin/teachers/:uid`
- `DELETE /api/admin/comments/:id`
- `DELETE /api/admin/links/:id`
- `POST /api/admin/sync/run`
- `GET /api/admin/sync/runs`

## 部署提示

生产环境需要设置后台口令：

```bash
npx wrangler secret put ADMIN_TOKEN
```

初始化远程 D1：

```bash
npm run d1:seed:remote
```

构建前端并部署 Worker：

```bash
cd /Users/pipi/Life/ZJU-mentor/zju-mentor-frontend
npm run build

cd /Users/pipi/Life/ZJU-mentor/cloudflare-backend
npx wrangler deploy
```
