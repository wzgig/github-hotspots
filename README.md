# GitHub Hotspots

[![Daily Hotspots](https://github.com/wzgig/github-hotspots/actions/workflows/daily.yml/badge.svg)](https://github.com/wzgig/github-hotspots/actions/workflows/daily.yml)
[![Weekly Hotspots](https://github.com/wzgig/github-hotspots/actions/workflows/weekly.yml/badge.svg)](https://github.com/wzgig/github-hotspots/actions/workflows/weekly.yml)
[![GitHub Pages](https://github.com/wzgig/github-hotspots/actions/workflows/pages.yml/badge.svg)](https://github.com/wzgig/github-hotspots/actions/workflows/pages.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[在线项目页面](https://wzgig.github.io/github-hotspots/) · [公开仓库](https://github.com/wzgig/github-hotspots)

一个可本地运行、也可由 GitHub Actions 定时执行的 GitHub 热点发现与内容生产流水线。它同时生成“综合主榜”和“AI 专题榜”：日榜各 Top 3、周榜各 Top 7，并把可审计的 GitHub 事实组织成榜单、中文审核稿和原创项目海报。

公开视觉采用原创的 `Signal Broadsheet / 开源热点编辑部·信号报`：技术报纸、Git 信号轨道和数据终端共同构成品牌，不复刻第三方账号的配色、版式或文案。GitHub API、GitHub Trending 和本地历史快照用于冻结榜单事实。

## 项目定位

GitHub Hotspots 定位为“可核验的开源情报内容引擎”，而不是让模型凭印象推荐仓库。它面向需要稳定日更/周更的中文技术内容运营者，也服务希望追溯榜单依据的开发者：同一份冻结事实驱动双榜排名、解释文案、原创海报和 Pages 展示，最终发布权始终由人工掌握。

## 主要能力

- 混合发现：GitHub Trending daily/weekly + GitHub REST Search。
- 元数据补全：仓库 ID、描述、语言、Star、Fork、Topics 和更新时间。
- 历史快照：按日期保存 JSON，逐步建立 1 日和 7 日增量基线。
- 双榜排名：综合主榜覆盖全部合格候选，AI 专题榜筛选 AI 候选后独立排名；同一仓库可以同时入榜。
- 可解释排名：两榜分别按 Star 增长、相对增长、Fork 增长、活跃度、累计 Star、Trending 信号六项评分。
- 确定性兜底：程序为每个仓库生成定位、增长、技术栈、规模、Topics、活跃度和来源 7 种候选；README 缺失或本地 Codex 不可用时仍能生成可审核文案。
- 可选 Codex 证据编辑：Prompt 4.1 / Schema 4.0 读取经过清洗的 README/metadata，在冻结身份、URL、排名和数字的前提下生成白话定位、最多 5 条能力、核心亮点、适合人群、前置条件、限制和许可证说明；每个自然语言字段必须绑定合法证据 ID。
- 内容产物：包含双榜的完整 Markdown、兼容旧消费者的结构化 JSON，以及综合榜/AI 榜两份独立的小红书审核稿。
- V4 Signal Broadsheet 海报：每榜生成 1 张封面，并为每个入榜仓库生成 1 张 `1200×1600` PNG；项目名左侧使用安全缓存的 GitHub Owner 头像，正文通过硬边报头、信号数据条和 01—05 Signal Rail 展示定位、五项能力、核心亮点与适合人群，失败时使用确定性身份块。
- 可靠降级：Trending 或 Search 单独失败时仍可继续；全部候选失效时返回非零退出码。
- 四层更新方式：本地 Codex 每天 07:30 生成日报、周日 08:45 生成周报；Actions 在 09:17 / 周日 10:27 提供无本机凭据的确定性兜底；也可手动触发或通过 CLI 按需运行。

```text
Trending + Search
        ↓
GitHub API 补全与过滤
        ↓
保存当日快照 ← 对比 1 日 / 7 日历史快照
        ↓
综合主榜排名 + AI token/phrase-aware 分类与独立排名
        ↓
清洗 README / metadata，生成确定性兜底与 7 个候选，安全缓存 Owner 头像
        ↓
确定性兜底 / 可选 Codex Prompt 4.1 整榜证据编辑
        ↓
Markdown + JSON + 两份小红书审核稿
        ↓
Signal Broadsheet 封面与逐项目海报
        ↓
publish/current 最新发布工作台 + publish/history 可追溯薄历史
```

## 更新频率

| 方式 | 当前能力 | 适合场景 |
| --- | --- | --- |
| 本地日报主链路 | 每天北京时间 07:30，并在用户登录时执行缺失补跑，使用当前用户的 Codex CLI | 生成 README 证据化日报和本地发布包 |
| 本地周报主链路 | 每周日北京时间 08:45，使用当前用户的 Codex CLI | 生成周日报告和本地发布包 |
| Actions 日报兜底 | 每天北京时间 09:17；仅在没有完整本地 Codex 日报时运行 | 电脑离线或 Codex 失败时保持连续更新 |
| Actions 周报兜底 | 每周日北京时间 10:27；仅在没有完整本地 Codex 周报时运行 | 周日连续性兜底 |
| Actions 手动触发 | 两个工作流均提供 `workflow_dispatch` | 外部故障恢复、按需刷新、发布前复核 |
| 本地 CLI | 可随时运行日榜、周榜或指定日期 | 调试、预览、人工运营 |

三种运行环境的语义不同：

| 模式 | 文案后端与失败语义 | 发布工作台与历史 |
| --- | --- | --- |
| 普通本地 CLI | 配置默认使用 `deterministic`；显式添加 `--editorial-backend codex-cli` 才调用本机 Codex。Codex 失败时 CLI 可以保留确定性回退结果供人工检查 | 报告命令不会自动打包；执行 `publish <report.json>` 后同时刷新本机 `current` 并写入 Git 可跟踪的 `history` |
| 已注册的本地计划任务 | 强制使用 `codex-cli`，两榜任一回退都会使严格门禁失败，不提交该次本地结果；稍后的 Actions 再负责连续性兜底 | 成功推送或确认远端已有同日期完整 Codex 报告与历史后，同步刷新本机对应周期目录；历史缺失时只修复历史，不重跑 Codex |
| GitHub Actions | 始终使用 `deterministic`，不能读取个人电脑上的 Codex 登录态 | 提交公开快照、报告、图片和 `publish/history`；不能直接写回离线电脑的 `publish/current` |

当前不默认启用小时级或“实时”提交。GitHub API 提供的是查询时刻的累计计数，本项目的增量又依赖按日期保存的快照；高频运行还需要重新设计同日多快照标识、并发写入、API 速率预算、历史保留和 Pages 发布节奏。在这些约束完成前，所谓“近实时”只能作为按需刷新，不应被描述为秒级 Star 事件流。

Windows 本地计划任务需要显式注册，默认不会因为安装依赖而自动修改系统：

```powershell
.\scripts\automation\register_tasks.ps1 -WhatIf
.\scripts\automation\register_tasks.ps1
```

任务以当前登录用户、低权限方式运行，只调用该用户已经登录的 Codex CLI；完整说明见 [docs/AUTOMATION.md](docs/AUTOMATION.md)。

## 快速开始

要求 Python 3.12。Windows PowerShell 示例：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

生成当天日榜：

```powershell
.\.venv\Scripts\python.exe -m github_hotspots.cli run --period daily
```

生成周榜或指定日期：

```powershell
.\.venv\Scripts\python.exe -m github_hotspots.cli run --period weekly
.\.venv\Scripts\python.exe -m github_hotspots.cli run --period daily --date 2026-07-11
.\.venv\Scripts\python.exe -m github_hotspots.cli run-all --date 2026-07-11
```

只用已经冻结的排名事实和报告内已有文案重新生成海报，不重新访问 GitHub：

```powershell
.\.venv\Scripts\python.exe -m github_hotspots.cli rerender reports/daily/2026-07-11.json
```

需要重新读取 README、许可证与 Owner 头像，并让本机 Codex 生成证据化的丰富文案时：

```powershell
.\.venv\Scripts\python.exe -m github_hotspots.cli rerender reports/daily/2026-07-11.json --refresh-evidence --editorial-backend codex-cli
```

生成打开即可发布的本地文件夹：

```powershell
.\.venv\Scripts\python.exe -m github_hotspots.cli publish reports/daily/2026-07-12.json
.\.venv\Scripts\python.exe -m github_hotspots.cli publish reports/weekly/2026-W28.json
```

完整图片工作台位于 `publish/current/`：日报和周报周期根目录各有共享的 `CHECKLIST.md` 与 `MANIFEST.json`，每个榜单帖子目录分别包含 `TITLE.txt`、`CAPTION.txt`、`REVIEW.md` 和按上传顺序编号的 `images/`。同一次命令还会写入 [发布历史索引](publish/history/INDEX.md)。

三层目录各有不同职责：`current` 是每个周期最新、带完整图片的上传工作台；被替换的本地包进入 `archive/<period>/<year>/<issue-stem>/`，用于保护人工修改；`history` 是提交 Git 的永久薄历史，保存每期标题、正文、审核稿、清单和图片哈希，但不重复复制 PNG，而是引用 `reports/.../assets/`。相同内容指纹重跑保持幂等，内容变化才产生新修订；旧日期默认不能覆盖较新的 `current`。

回填旧期但不改变当前工作台，或重建历史索引：

```powershell
.\.venv\Scripts\python.exe -m github_hotspots.cli publish reports/daily/2026-07-12.json --history-only
.\.venv\Scripts\python.exe -m github_hotspots.cli publish-history-index
```

只有明确需要把旧期重新放进工作台时才使用 `--activate-older`。`history` 保存的是自动生成基线；之后在 `current` 中做的人工改稿不会自动提交，仍应自行备份最终发布版。

> [!TIP]
> 公共仓库查询可以无 Token 运行，但更容易遇到 GitHub API 限流。本地可在环境变量 `GITHUB_TOKEN` 中放置只读 Token；GitHub Actions 会自动使用仓库自带的 Token。

## 输出

```text
data/snapshots/YYYY-MM-DD.json
reports/daily/YYYY-MM-DD.md
reports/daily/YYYY-MM-DD.json
reports/daily/YYYY-MM-DD.xiaohongshu.md
reports/daily/YYYY-MM-DD.ai.xiaohongshu.md
reports/daily/avatars/YYYY-MM-DD/*.png
reports/weekly/YYYY-Www.md
reports/weekly/YYYY-Www.json
reports/weekly/YYYY-Www.xiaohongshu.md
reports/weekly/YYYY-Www.ai.xiaohongshu.md
reports/weekly/avatars/YYYY-Www/*.png
publish/current/TODAY.md
publish/current/daily/{01-comprehensive,02-ai}/
publish/current/weekly/{01-comprehensive,02-ai}/
publish/history/INDEX.{json,md}
publish/history/<period>/<year>/<report-stem>/<revision>/
```

默认图像输出契约是：综合榜与 AI 榜分别生成 1 张封面和每个入榜项目 1 张 `1200×1600` PNG；配置也支持 `600×800` 至 `2400×3200` 范围内的其他合法 3:4 尺寸。图片集中放在当期报告的资产目录中，并用 Schema 2 `manifest.json` 记录实际尺寸、生成器、样式、源报告、窗口、Top N 和每项资产。例如：

```text
reports/daily/assets/YYYY-MM-DD/
  YYYY-MM-DD.comprehensive.cover.png
  YYYY-MM-DD.comprehensive.01.owner--repo.png
  YYYY-MM-DD.ai.cover.png
  YYYY-MM-DD.ai.01.owner--repo.png
  manifest.json

reports/weekly/assets/YYYY-Www/
  YYYY-Www.comprehensive.cover.png
  YYYY-Www.comprehensive.01.owner--repo.png
  YYYY-Www.ai.cover.png
  YYYY-Www.ai.01.owner--repo.png
  manifest.json
```

上述接口已经接入报告 JSON、日/周工作流和 Pages 构建；Schema 2 `manifest.json` 记录 renderer 名称/版本、`style_version`、`source_report`、统计窗口和 Top N。Owner 头像从 GitHub 元数据取得后会限制来源、体积和像素，使用 Pillow 去除元数据并重编码为本地 PNG；失败时海报自动使用确定性身份块。网站会为上榜项目提供海报预览与 PNG 下载，文案和海报仍全部属于人工审核稿。

海报确定性以“相同报告输入、渲染器与样式版本、同一字体文件和同一渲染环境”为边界。Windows 与 GitHub Actions 可以使用不同的合格中文字体，因此跨系统的字体栅格和 PNG 字节不保证完全相同；缺少中文字体或所需字形时，渲染应直接失败并提示安装字体。

当前真实样例的日榜图片约 `1.49 MiB`、周榜约 `3.25 MiB`。按现有节奏估算，图片资产每年可能接近 `700 MiB`，Git 历史占用还会更高。后续需要确定“主分支只保留近期资产、旧资产转入 Release 或外部静态存储”的保留策略；策略落地前不静默删除历史图片。

报告 JSON 的顶层 `repositories` 继续表示综合主榜，以兼容现有消费者；`boards.comprehensive.repositories` 和 `boards.ai.repositories` 分别保存两榜的独立排名。

仓库已包含真实运行样例：[2026-07-12 日榜](reports/daily/2026-07-12.md)、[2026-W28 周榜](reports/weekly/2026-W28.md)与[可查找的发布历史](publish/history/INDEX.md)。

## 数据口径

公开文案会明确区分三类增长来源：

| `delta_source` | 含义 | 对外表述 |
| --- | --- | --- |
| `snapshot` | 当前计数减去 1 日或 7 日历史快照 | 快照净增 Star |
| `trending` | GitHub Trending 页面展示的 `stars today/this week` | Trending 周期 Star |
| `estimate` | 首次运行时的历史平均速度估算 | 必须标“约”或“估算”，不计入增长评分 |

估算值只用于提供上下文，不参与 Star/Fork 增长分，因此不会压过可观察的快照或 Trending 信号。热度分是本项目自己的排序方法，不是 GitHub 官方排名。

## 配置

主要入口是 [config/hotspots.yaml](config/hotspots.yaml)：

- `boards.comprehensive`：综合主榜开关、名称和日/周 Top N，默认 Top 3 / Top 7。
- `boards.ai`：AI 专题榜开关、名称、日/周 Top N、精确 Topics 和 token/phrase-aware 关键词，默认 Top 3 / Top 7。
- `sources`：启停 Trending、Search，设置候选数量与查询。
- `filters`：最低 Star、描述要求及语言/Owner/仓库黑名单。
- `ranking.weights`：六项排名权重，合计必须为 1.0。
- `outputs`：快照和报告目录。
- `editorial`：确定性文案或本地 `codex-cli` Prompt 4.1 / Schema 4.0 证据编辑后端、超时、提示词和 Schema；默认 `deterministic`，CI 不启用本地 Codex。
- `posters`：确定性海报开关与 3:4 尺寸；本次升级约定为 `1200×1600`。
- `publication`：首发日期、`publish` 根目录与标题/正文长度门禁；2026-07-12 对应 `D001`、`W001`。

## GitHub Actions

- [.github/workflows/daily.yml](.github/workflows/daily.yml)：每日北京时间 09:17 的确定性兜底。
- [.github/workflows/weekly.yml](.github/workflows/weekly.yml)：每周日北京时间 10:27 的确定性兜底。

两个工作流都支持在 GitHub 仓库的 **Actions** 页面通过 **Run workflow** 手动触发。工作流会安装项目、运行测试、生成产物，并只提交 `data/snapshots`、对应报告目录和 `publish/history` 薄历史。报告存在但历史缺失、索引不一致或同指纹修订损坏时，工作流只重建历史，不覆盖已经完成的 Codex 文案。需要在仓库设置中允许 Actions 对内容进行写入。

## 提示词与产品说明

- [重构后的项目总控提示词](prompts/project_master_prompt_zh.md)
- [仓库中文卡片摘要提示词](prompts/repository_summary_zh.md)
- [小红书参考拆解](docs/REFERENCE_ANALYSIS.md)
- [产品规格与验收标准](docs/PRODUCT_SPEC.md)
- [完整项目规划](docs/PROJECT_PLAN.md)
- [持续运维与发布规范](docs/OPERATIONS.md)
- [中国地区 Chrome Extension 安装与替代方案](docs/CHROME_EXTENSION_SETUP_CN.md)
- [本地 Codex API 安全接入方案](docs/LOCAL_CODEX_API.md)
- [本地 Codex 定时自动化](docs/AUTOMATION.md)
- [发布运营手册](docs/PUBLISHING_PLAYBOOK.md)
- [本地发布工作台](publish/README.md)

普通本地 CLI 的配置默认使用确定性摘要，不依赖模型；本地计划任务会显式选择 `codex-cli`，GitHub Actions 则固定使用 `deterministic`。显式启用 `--refresh-evidence --editorial-backend codex-cli` 后，工作流会读取经过大小限制和清洗的 README，并让本机 Codex 在冻结仓库身份、URL、排名和数字事实的前提下生成白话定位、最多 5 条能力、核心亮点、适合人群、前置条件、限制和许可证说明。每个自然语言字段都必须引用本批次存在的证据 ID；许可证缺失或为 `NOASSERTION` 时不得猜成 MIT。README 缺失时，该仓库只能逐字段使用同一受控候选；违反约束或任一输出校验失败时整榜回退。项目只调用已安装的 `codex exec`，不会读取、复制或提交用户级 provider 配置与凭据。

CLI 不可用、超时、非法 JSON/Schema/证据 ID、README SHA/许可证/冻结事实不匹配或其他校验失败时，整榜自动回退确定性文案。GitHub Actions 默认使用 `deterministic`，不依赖本机 Codex，也不会复制本机凭据。

项目只允许调用已安装的 `codex` 命令，由 Codex CLI 自行使用其用户级配置和认证。项目不会扫描、解析、复制或提交本地 Codex 配置、API 凭据、浏览器登录态或实际 provider 信息。

## 当前边界与下一阶段

当前发布链路止于“生成内容包”：两榜文案以及原创海报都由用户人工核验、选图和发布，系统不会自动登录或发布到小红书。未来如建设自动发布，必须作为新的独立阶段再次获得明确授权，并满足平台规则、审核门禁和可撤回要求。

文案自然度由 Prompt 4.1 的 3/10/30 秒阅读任务、证据化白话编辑和确定性兜底共同保证。后续重点是扩大固定评估集、记录前三期的收藏/评论反馈、改进证据对照审核并监控许可证准确性与整榜回退率；自动发布仍不在当前范围。

## 持续交付约定

项目级 [AGENTS.md](AGENTS.md) 规定了后续每次变更的固定闭环：更新 `PROJECT_LOG.md`、运行测试与 Ruff、检查敏感信息、创建 Conventional Commit、推送 `origin/main`，并验证对应 Actions 与 GitHub Pages 部署。除非用户明确改变策略，小红书内容始终先人工审核再发布。

## 许可证

本项目采用 [MIT License](LICENSE)。它简洁、宽松，适合希望被学习、复用和二次开发的轻量 Python 自动化项目；当前未识别出必须采用 Apache-2.0 明示专利条款和 NOTICE 机制的需求。

你可以将代码用于个人或商业用途，也可以修改、合并、发布和分发；在复制或分发本软件及其主要部分时，必须保留原始版权声明和 MIT 许可声明。软件按“原样”提供，不附带担保。
