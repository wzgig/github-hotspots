# GitHub Hotspots

[![Daily Hotspots](https://github.com/wzgig/github-hotspots/actions/workflows/daily.yml/badge.svg)](https://github.com/wzgig/github-hotspots/actions/workflows/daily.yml)
[![Weekly Hotspots](https://github.com/wzgig/github-hotspots/actions/workflows/weekly.yml/badge.svg)](https://github.com/wzgig/github-hotspots/actions/workflows/weekly.yml)
[![GitHub Pages](https://github.com/wzgig/github-hotspots/actions/workflows/pages.yml/badge.svg)](https://github.com/wzgig/github-hotspots/actions/workflows/pages.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[在线项目页面](https://wzgig.github.io/github-hotspots/) · [公开仓库](https://github.com/wzgig/github-hotspots)

一个可本地运行、也可由 GitHub Actions 定时执行的 GitHub 热点发现与内容生产流水线。它同时生成“综合主榜”和“AI 专题榜”：日榜各 Top 3、周榜各 Top 7，并把可审计的 GitHub 事实组织成榜单、中文审核稿和原创项目海报。

项目参考了用户提供的小红书“GitHub 爆火项目榜”的信息层级和阅读比例，但不复制原作者的图片、账号标识或文案。GitHub API、GitHub Trending 和本地历史快照用于冻结榜单事实。

## 项目定位

GitHub Hotspots 定位为“可核验的开源情报内容引擎”，而不是让模型凭印象推荐仓库。它面向需要稳定日更/周更的中文技术内容运营者，也服务希望追溯榜单依据的开发者：同一份冻结事实驱动双榜排名、解释文案、原创海报和 Pages 展示，最终发布权始终由人工掌握。

## 主要能力

- 混合发现：GitHub Trending daily/weekly + GitHub REST Search。
- 元数据补全：仓库 ID、描述、语言、Star、Fork、Topics 和更新时间。
- 历史快照：按日期保存 JSON，逐步建立 1 日和 7 日增量基线。
- 双榜排名：综合主榜覆盖全部合格候选，AI 专题榜筛选 AI 候选后独立排名；同一仓库可以同时入榜。
- 可解释排名：两榜分别按 Star 增长、相对增长、Fork 增长、活跃度、累计 Star、Trending 信号六项评分。
- 确定性兜底：程序为每个仓库生成定位、增长、技术栈、规模、Topics、活跃度和来源 7 种候选；README 缺失或本地 Codex 不可用时仍能生成可审核文案。
- 可选 Codex 证据编辑：Prompt/Schema 4.0 读取经过清洗的 README/metadata，在冻结身份、URL、排名和数字的前提下生成白话定位、最多 5 条能力、核心亮点、适合人群、前置条件、限制和许可证说明；每个自然语言字段必须绑定合法证据 ID。
- 内容产物：包含双榜的完整 Markdown、兼容旧消费者的结构化 JSON，以及综合榜/AI 榜两份独立的小红书审核稿。
- V3 原创海报：每个榜单生成 1 张封面，并为每个入榜仓库生成 1 张 `1200×1600` 的 3:4 PNG；项目名左侧使用经过安全缓存和重新编码的 GitHub Owner 头像，正文按“身份—四项统计—最多 5 条能力—核心亮点—适合谁”组织，失败时使用确定性占位图。
- 可靠降级：Trending 或 Search 单独失败时仍可继续；全部候选失效时返回非零退出码。
- 三种更新方式：每日北京时间 08:17、每周一 08:27 自动运行，也可从 Actions 页面手动触发或通过本地 CLI 按需运行。

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
确定性兜底 / 可选 Codex Prompt 4.0 整榜证据编辑
        ↓
Markdown + JSON + 两份小红书审核稿
        ↓
确定性封面与逐项目海报
```

## 更新频率

| 方式 | 当前能力 | 适合场景 |
| --- | --- | --- |
| 每日定时 | 每天北京时间 08:17 运行日榜工作流 | 稳定日更、积累 1 日快照 |
| 每周定时 | 每周一北京时间 08:27 运行周榜工作流 | 周度复盘、计算 7 日窗口 |
| Actions 手动触发 | 两个工作流均提供 `workflow_dispatch` | 外部故障恢复、按需刷新、发布前复核 |
| 本地 CLI | 可随时运行日榜、周榜或指定日期 | 调试、预览、人工运营 |

当前不默认启用小时级或“实时”提交。GitHub API 提供的是查询时刻的累计计数，本项目的增量又依赖按日期保存的快照；高频运行还需要重新设计同日多快照标识、并发写入、API 速率预算、历史保留和 Pages 发布节奏。在这些约束完成前，所谓“近实时”只能作为按需刷新，不应被描述为秒级 Star 事件流。

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
```

本次图像升级的输出契约是：综合榜与 AI 榜分别生成 1 张封面和每个入榜项目 1 张 `1200×1600` PNG，集中放在当期报告的资产目录中，并用 Schema 2 `manifest.json` 记录生成器、样式、源报告、窗口、Top N 和每项资产。例如：

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

当前样例的日榜图片约 `1 MB`、周榜图片约 `2 MB`，日周合计约 `3 MB`。按每年 365 份日榜、52 份周榜并预留清单与体积波动，容量规划采用约 `495 MB/年`；Git 历史占用还可能更高。v1.2 将确定“主分支保留近期资产、旧资产归档到 Release 或外部静态存储、清单保留可追溯链接”的策略；策略落地前不静默删除历史图片，并持续监控仓库大小。

报告 JSON 的顶层 `repositories` 继续表示综合主榜，以兼容现有消费者；`boards.comprehensive.repositories` 和 `boards.ai.repositories` 分别保存两榜的独立排名。

仓库已包含真实运行样例：[2026-07-11 日榜](reports/daily/2026-07-11.md)和 [2026-W28 周榜](reports/weekly/2026-W28.md)。

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
- `editorial`：确定性文案或本地 `codex-cli` Prompt/Schema 4.0 证据编辑后端、超时、提示词和 Schema；默认 `deterministic`，CI 不启用本地 Codex。
- `posters`：确定性海报开关与 3:4 尺寸；本次升级约定为 `1200×1600`。

## GitHub Actions

- [.github/workflows/daily.yml](.github/workflows/daily.yml)：每日北京时间 08:17。
- [.github/workflows/weekly.yml](.github/workflows/weekly.yml)：每周一北京时间 08:27。

两个工作流都支持在 GitHub 仓库的 **Actions** 页面通过 **Run workflow** 手动触发。工作流会安装项目、运行测试、生成产物，然后只提交 `data/snapshots` 和对应报告目录。需要在仓库设置中允许 Actions 对内容进行写入。

## 提示词与产品说明

- [重构后的项目总控提示词](prompts/project_master_prompt_zh.md)
- [仓库中文卡片摘要提示词](prompts/repository_summary_zh.md)
- [小红书参考拆解](docs/REFERENCE_ANALYSIS.md)
- [产品规格与验收标准](docs/PRODUCT_SPEC.md)
- [完整项目规划](docs/PROJECT_PLAN.md)
- [持续运维与发布规范](docs/OPERATIONS.md)
- [中国地区 Chrome Extension 安装与替代方案](docs/CHROME_EXTENSION_SETUP_CN.md)
- [本地 Codex API 安全接入方案](docs/LOCAL_CODEX_API.md)

默认后端继续使用确定性摘要，不依赖模型。显式启用 `--refresh-evidence --editorial-backend codex-cli` 后，工作流会读取经过大小限制和清洗的 README，并让本机 Codex 在冻结仓库身份、URL、排名和数字事实的前提下生成白话定位、最多 5 条能力、核心亮点、适合人群、前置条件、限制和许可证说明。每个自然语言字段都必须引用本批次存在的证据 ID；许可证缺失或为 `NOASSERTION` 时不得猜成 MIT。README 缺失时，该仓库只能逐字段使用同一受控候选；违反约束或任一输出校验失败时整榜回退。项目只调用已安装的 `codex exec`，不会读取、复制或提交用户级 provider 配置与凭据。

CLI 不可用、超时、非法 JSON/Schema/证据 ID、README SHA/许可证/冻结事实不匹配或其他校验失败时，整榜自动回退确定性文案。GitHub Actions 默认使用 `deterministic`，不依赖本机 Codex，也不会复制本机凭据。

项目只允许调用已安装的 `codex` 命令，由 Codex CLI 自行使用其用户级配置和认证。项目不会扫描、解析、复制或提交本地 Codex 配置、API 凭据、浏览器登录态或实际 provider 信息。

## 当前边界与下一阶段

当前发布链路止于“生成内容包”：两榜文案以及原创海报都由用户人工核验、选图和发布，系统不会自动登录或发布到小红书。未来如建设自动发布，必须作为新的独立阶段再次获得明确授权，并满足平台规则、审核门禁和可撤回要求。

文案自然度由 Prompt 4.0 的证据化白话编辑和确定性兜底共同保证。后续重点是扩大固定评估集、改进证据对照审核、监控许可证准确性与整榜回退率；自动发布仍不在当前范围。

## 持续交付约定

项目级 [AGENTS.md](AGENTS.md) 规定了后续每次变更的固定闭环：更新 `PROJECT_LOG.md`、运行测试与 Ruff、检查敏感信息、创建 Conventional Commit、推送 `origin/main`，并验证对应 Actions 与 GitHub Pages 部署。除非用户明确改变策略，小红书内容始终先人工审核再发布。

## 许可证

本项目采用 [MIT License](LICENSE)。它简洁、宽松，适合希望被学习、复用和二次开发的轻量 Python 自动化项目；当前未识别出必须采用 Apache-2.0 明示专利条款和 NOTICE 机制的需求。

你可以将代码用于个人或商业用途，也可以修改、合并、发布和分发；在复制或分发本软件及其主要部分时，必须保留原始版权声明和 MIT 许可声明。软件按“原样”提供，不附带担保。
