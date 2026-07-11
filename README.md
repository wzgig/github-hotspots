# GitHub Hotspots

[![Daily Hotspots](https://github.com/wzgig/github-hotspots/actions/workflows/daily.yml/badge.svg)](https://github.com/wzgig/github-hotspots/actions/workflows/daily.yml)
[![Weekly Hotspots](https://github.com/wzgig/github-hotspots/actions/workflows/weekly.yml/badge.svg)](https://github.com/wzgig/github-hotspots/actions/workflows/weekly.yml)
[![GitHub Pages](https://github.com/wzgig/github-hotspots/actions/workflows/pages.yml/badge.svg)](https://github.com/wzgig/github-hotspots/actions/workflows/pages.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[在线项目页面](https://wzgig.github.io/github-hotspots/) · [公开仓库](https://github.com/wzgig/github-hotspots)

一个可本地运行、也可由 GitHub Actions 定时执行的 GitHub 热点发现与内容生成流水线。它同时生成“综合主榜”和“AI 专题榜”：日榜各 Top 3、周榜各 Top 7，并输出可审计的 JSON、Markdown 榜单和两份小红书文案素材。

项目参考了用户提供的小红书“GitHub 爆火项目榜”的信息结构，但不复制原作者的图片、版式或文案。GitHub API、GitHub Trending 和本地历史快照才是数据来源。

## 主要能力

- 混合发现：GitHub Trending daily/weekly + GitHub REST Search。
- 元数据补全：仓库 ID、描述、语言、Star、Fork、Topics 和更新时间。
- 历史快照：按日期保存 JSON，逐步建立 1 日和 7 日增量基线。
- 双榜排名：综合主榜覆盖全部合格候选，AI 专题榜筛选 AI 候选后独立排名；同一仓库可以同时入榜。
- 可解释排名：两榜分别按 Star 增长、相对增长、Fork 增长、活跃度、累计 Star、Trending 信号六项评分。
- 三种产物：包含双榜的完整 Markdown、兼容旧消费者的结构化 JSON，以及综合榜/AI 榜两份小红书文案。
- 可靠降级：Trending 或 Search 单独失败时仍可继续；全部候选失效时返回非零退出码。
- 自动运行：每日北京时间 08:17、每周一 08:27 运行并提交新产物。

```text
Trending + Search
        ↓
GitHub API 补全与过滤
        ↓
保存当日快照 ← 对比 1 日 / 7 日历史快照
        ↓
综合主榜排名 + AI token/phrase-aware 分类与独立排名
        ↓
Markdown + JSON + 两份小红书文案
```

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

> [!TIP]
> 公共仓库查询可以无 Token 运行，但更容易遇到 GitHub API 限流。本地可在环境变量 `GITHUB_TOKEN` 中放置只读 Token；GitHub Actions 会自动使用仓库自带的 Token。

## 输出

```text
data/snapshots/YYYY-MM-DD.json
reports/daily/YYYY-MM-DD.md
reports/daily/YYYY-MM-DD.json
reports/daily/YYYY-MM-DD.xiaohongshu.md
reports/daily/YYYY-MM-DD.ai.xiaohongshu.md
reports/weekly/YYYY-Www.md
reports/weekly/YYYY-Www.json
reports/weekly/YYYY-Www.xiaohongshu.md
reports/weekly/YYYY-Www.ai.xiaohongshu.md
```

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

## GitHub Actions

- [.github/workflows/daily.yml](.github/workflows/daily.yml)：每日北京时间 08:17。
- [.github/workflows/weekly.yml](.github/workflows/weekly.yml)：每周一北京时间 08:27。

工作流会安装项目、运行测试、生成产物，然后只提交 `data/snapshots` 和对应报告目录。需要在仓库设置中允许 Actions 对内容进行写入。

## 提示词与产品说明

- [重构后的项目总控提示词](prompts/project_master_prompt_zh.md)
- [仓库中文卡片摘要提示词](prompts/repository_summary_zh.md)
- [小红书参考拆解](docs/REFERENCE_ANALYSIS.md)
- [产品规格与验收标准](docs/PRODUCT_SPEC.md)
- [完整项目规划](docs/PROJECT_PLAN.md)
- [持续运维与发布规范](docs/OPERATIONS.md)
- [中国地区 Chrome Extension 安装与替代方案](docs/CHROME_EXTENSION_SETUP_CN.md)
- [本地 Codex API 安全接入方案](docs/LOCAL_CODEX_API.md)

运行时默认使用不依赖 LLM 的事实型摘要器。后续接入模型时，应使用结构化摘要提示词，并在程序侧校验 JSON、数字和 URL，模型不得自行搜索或补造事实。

## 当前边界与下一阶段

当前阶段只生成小红书文案，由用户人工核验事实、修改表达并发布；不会自动登录或发布到小红书，也不生成 PNG 海报。未来如建设自动发布，必须作为新的独立阶段再次获得明确授权，并满足平台规则、审核门禁和可撤回要求。

规则型摘要会保留 GitHub 原始英文描述以避免错误翻译；需要更自然的全中文卡片时，可接入受事实约束的 LLM 摘要器。

## 持续交付约定

项目级 [AGENTS.md](AGENTS.md) 规定了后续每次变更的固定闭环：更新 `PROJECT_LOG.md`、运行测试与 Ruff、检查敏感信息、创建 Conventional Commit、推送 `origin/main`，并验证对应 Actions 与 GitHub Pages 部署。除非用户明确改变策略，小红书内容始终先人工审核再发布。

## 许可证

本项目采用 [MIT License](LICENSE)。它简洁、宽松，适合希望被学习、复用和二次开发的轻量 Python 自动化项目；当前未识别出必须采用 Apache-2.0 明示专利条款和 NOTICE 机制的需求。

你可以将代码用于个人或商业用途，也可以修改、合并、发布和分发；在复制或分发本软件及其主要部分时，必须保留原始版权声明和 MIT 许可声明。软件按“原样”提供，不附带担保。
