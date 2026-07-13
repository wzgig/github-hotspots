# GitHub Hotspots 发布运营手册

## 1. 产品定位

GitHub Hotspots 不是另一个只列 Star 数字的热榜，而是一份帮助中文读者快速看懂开源项目的编辑型产品：先回答“它替谁完成什么”，再解释“为什么进入本期榜单”。

固定产品范围：

- 综合主榜：跨领域比较 GitHub 热点；
- AI 专题榜：在 AI 候选池内独立排名；
- 日报：每天一期，从 2026-07-12 的 `D001` 开始；
- 周报：每周日一期，从 2026-W28 的 `W001` 开始；
- 小红书只生成审核稿、可粘贴正文和配图，最终由人工发布。

## 2. 原创品牌：Signal Broadsheet

公开海报采用“开源热点编辑部·信号报”风格，与项目页面保持同一品牌：

- 视觉母版：米色纸张、黑色油墨、信号橙与酸绿色；
- 记忆元素：硬边报头、排名胶带、数据终端和 Git 式 Signal Rail；
- 综合榜：浅色热力格；AI 榜：深色雷达；
- 日报固定显示 `24H / Dxxx`，周报固定显示 `7D / Wxxx`；
- 每张项目卡按照“白话定位 → 信号数据 → 五项能力 → 核心亮点 → 适合人群”阅读；
- 禁止恢复旧版深绿头部、圆形排名章、四格仪表盘和左右深浅分栏组合。

## 3. 自动化运行模型

| 层级 | 北京时间 | 后端 | 作用 |
| --- | --- | --- | --- |
| 本地日报主链路 | 每天 07:30 | 当前用户的 `codex exec` | 生成高质量 README 证据化日报 |
| 本地周报主链路 | 周日 08:45 | 当前用户的 `codex exec` | 生成本周周报 |
| Actions 日报兜底 | 每天 09:17 | deterministic | 本地没有完整 Codex 日报时补齐 |
| Actions 周报兜底 | 周日 10:27 | deterministic | 本地没有完整 Codex 周报时补齐 |

本地计划任务只调用已安装的 Codex CLI。API endpoint、My Codex 密钥、provider 和用户配置由 Codex 自己管理，项目不读取、不复制、不写入日志，也不上传 GitHub Secrets。

本地任务使用独立临时 worktree，不会清理、重置或 rebase IDE 中的工作区。两项任务共享运行锁；任何测试失败、Codex 回退、可疑文件或推送冲突都会停止提交，稍后的 Actions 再提供确定性兜底。

## 4. 每期出版流水线

```text
GitHub Trending / REST Search
→ 冻结仓库身份、排名与数值事实
→ 收集并清洗 README、许可证和 Owner 头像
→ 本地 Codex 按 Prompt 4.1 生成证据化中文文案
→ 严格回查身份、数字、README SHA、许可证与证据 ID
→ 渲染 Signal Broadsheet 海报
→ 生成 publish/current 最新工作台与 publish/history 永久薄历史
→ 自动检查标题、正文、图片顺序、尺寸与哈希
→ 人工审核
→ 人工发布
→ 记录 24h / 7d 表现并进入下一期复盘
```

质量门禁：

1. 综合榜和 AI 榜都必须存在；
2. 本地主链路要求两榜均为 `used_backend=codex-cli` 且 `fallback_used=false`；
3. 排名、URL、Star、Fork、增量、日期和许可证不得由模型改写；
4. 每个项目最多五条互不重复能力，优先使用“对象 + 动作 + 结果”；
5. 所有项目图必须使用 Manifest 声明的合法 3:4 PNG 尺寸（默认 `1200×1600`），Owner 头像失败时只能使用稳定身份块；
6. 可粘贴正文不得包含 Markdown 内部标题、报告路径、配图清单或审核说明；
7. 小红书发布前必须阅读对应 `REVIEW.md` 与 `CHECKLIST.md`。

## 5. `publish` 发布工作台

手动生成：

```powershell
.\.venv\Scripts\python.exe -m github_hotspots.cli publish reports/daily/2026-07-12.json
.\.venv\Scripts\python.exe -m github_hotspots.cli publish reports/weekly/2026-W28.json
```

正常 `publish` 会同时刷新本机最新工作台和 Git 跟踪的历史。回填旧期但不改变当前工作台时使用：

```powershell
.\.venv\Scripts\python.exe -m github_hotspots.cli publish `
  reports/daily/2026-07-12.json --history-only
```

打开 `publish/current/TODAY.md` 后，先进入日报或周报周期目录。周期根目录包含：

- `CHECKLIST.md`：这一期两个帖子的共享发布检查清单；
- `MANIFEST.json`：来源报告、编辑后端、图片哈希、期号和两个帖子目录的机器可读清单。

再进入 `01-comprehensive/` 或 `02-ai/` 帖子目录：

- `TITLE.txt`：复制标题；
- `CAPTION.txt`：复制正文与标签；
- `images/`：按数字前缀依次上传；
- `REVIEW.md`：核对项目事实、许可证和图片顺序。

所有自动生成的帖子初始状态都是 `draft`。当前项目没有“批准并发布”的 CLI 命令，也不会自动改写小红书状态；`approved` 只表示人工已经完成事实、图片、标题和平台合规复核。操作时勾选共享 `CHECKLIST.md`，并在 `REVIEW.md` 或独立运营记录中补充发布时间和帖子链接。不要为了看起来已批准而直接篡改来源哈希或编辑后端字段。

目录分为三层：

- `current`：最新日报与最新周报的完整图片工作台；
- `archive`：被替换的本地包和人工修改备份，不进入 Git；
- `history`：每期自动生成基线的 Git 永久记录，保存标题、正文、审核稿、清单和图片引用，不复制 PNG。

旧的 `current/<period>` 在内容变化时移动到 `archive/<period>/<year>/<issue-stem>/`，相同指纹重跑不会制造重复副本。如果 `D001-A` 延后到 `D002` 之后发布，人工改过的版本应从本机 `archive` 找回；未改动的生成基线也可以从 [历史索引](../publish/history/INDEX.md) 查阅。旧日期默认不能覆盖较新的 `current`；只有明确需要时才使用 `--activate-older`。对 `current` 的人工改稿不会自动进入 `history`，最终发布版仍应另行备份。

## 6. 第一周发布节奏

2026-07-12 是周日，也是日报与周报的公开首发日。建议不要在同一天连续发布四篇：

1. 上午发布 `D001-C` 日报综合榜；
2. 晚些时候发布 `W001-C` 周报综合榜；
3. `D001-A` 和 `W001-A` 作为独立 AI 帖子，留到后续时段或根据评论需求发布；跨过下一次同周期生成时间时，从本机 `archive/` 找回人工版，或从 `publish/history/INDEX.md` 查找生成基线；
4. 第一周先验证读者是否更愿意收藏“用途解释”还是“上手教程”，不要过早增加发帖频率。

## 7. 人工复盘指标

每个帖子在发布后记录 24 小时和 7 天数据：

- 曝光或阅读量；
- 点赞、收藏、评论、分享；
- 新增关注；
- 收藏率与评论率；
- 评论中被点名要求继续讲解的项目；
- 标题、首图、项目数量和发布时间。

前三期只做单变量实验：一次只改变标题结构、封面钩子、项目数量或发布时间中的一项。优先看收藏和有效评论，不以单次曝光量判断内容方向。

## 8. 当前边界

- 电脑关机或用户未登录时，本地 Codex 计划任务不保证运行；Actions 会稍后兜底。
- Actions 不能使用只存在于个人电脑的 Codex 登录态或 My Codex 密钥。
- Actions 兜底更新公开报告、图片、Pages 数据与 `publish/history`，但不能把 `publish/current` 写回一台离线的个人电脑；本地完整图片工作台需要由本地计划任务同步，或在拉取报告后手动运行 `publish` 命令。
- 周榜增长仍可能来自明确标注的 GitHub Trending 周期 Star，而非精确 7 日快照净增。
- 项目不会自动登录、发布、回复评论或操作小红书账号。
- 小红书平台表现仍需人工记录；自动读取平台数据和自动发布属于未来单独授权范围。
