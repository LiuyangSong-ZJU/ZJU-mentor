# Cloudflare 改造清单

## 目标

在当前仓库内新增 `cloudflare-backend/` 子目录，实现一套 Cloudflare 原生后端，覆盖当前 Python 版本的：

- 爬取单位与导师数据
- 构建与更新数据库
- 为前端提供 `/api/*`
- 后台管理与删除评论/链接
- 定时自动同步

## 现有文件到新实现的映射

- `/Users/pipi/Life/ZJU-mentor/local_api_server.py`
  - 对应：
    - `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/src/routes/public.ts`
    - `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/src/routes/admin.ts`
    - `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/src/services/publicService.ts`
    - `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/src/services/adminService.ts`

- `/Users/pipi/Life/ZJU-mentor/build_database.py`
  - 对应：
    - `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/migrations/0001_init.sql`
    - `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/scripts/seed-from-json.ts`

- `/Users/pipi/Life/ZJU-mentor/incremental_update_db.py`
  - 对应：
    - `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/src/services/syncService.ts`
    - `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/src/routes/ingest.ts`

- `/Users/pipi/Life/ZJU-mentor/get_colleges.py`
  - 对应：
    - `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/src/services/syncService.ts`
    - `fetchLatestColleges()`

- `/Users/pipi/Life/ZJU-mentor/get_all_teachers.py`
  - 对应：
    - `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/src/services/syncService.ts`
    - `fetchLatestTeachers()`

- `/Users/pipi/Life/ZJU-mentor/test/test_incremental_update.py`
  - 下一步建议迁移到：
    - `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/test/sync.test.ts`

## 这次已经落下来的骨架

- 新建 Cloudflare Worker 项目结构
- 新建 D1 schema 和索引
- 新建 Worker 路由分层
- 新建增量同步服务层
- 新建手动同步与最近同步记录接口
- 让前端开发代理默认指向 Worker 本地端口

## 下一轮建议继续做的具体文件

1. 完善 `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/src/services/syncService.ts`
   - 把 Browser Run 抓取的分页兜底和异常重试做完整

2. 新增 `/Users/pipi/Life/ZJU-mentor/cloudflare-backend/test/sync.test.ts`
   - 把 Python 版增量规则回归测试迁成 TS

3. 新增 SQLite 迁移工具
   - 建议路径：`/Users/pipi/Life/ZJU-mentor/cloudflare-backend/scripts/export-comments-and-links.py`
   - 作用：把旧 `zju_teachers.db` 的评论与链接导出为 JSON/SQL，再导入 D1

4. 如果要和前端一起上 Cloudflare
   - 先执行 `zju-mentor-frontend` 的构建
   - 再由 Worker `assets` 同源托管

## 当前风险点

- 抓取链路对目标站页面结构仍有依赖
- Worker + Browser Run 的抓取成功率需要一次真实联调验证
- 当前首字母分组与 pinyin 搜索先做了简化版，后续建议补齐
