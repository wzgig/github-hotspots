# GitHub Hotspots 产品规格说明

## 1. 执行摘要

### 问题陈述

人工查找 GitHub 热门项目、核对 Star 增量、整理中文亮点并排成日榜/周榜，重复且容易出现数字口径不一致、引用缺失和模型编造。用户需要一个可以本地运行、也可以由 GitHub Actions 定时运行的可审计流程。

### 方案概述

构建一个 Python 3.12 的开源情报与内容生产项目，从 GitHub Trending、GitHub Search 和 GitHub API 获取候选与事实，按日/周保存快照并计算真实增量。系统对全部合格候选生成“综合主榜”，对 AI 候选生成独立专题榜；日榜各 Top 3、周榜各 Top 7。系统输出双榜 Markdown/JSON、审核稿、Signal Broadsheet V4 海报和 `publish/current` 可发布文件夹。默认使用确定性文案；本地主链路可通过 Prompt 4.1 / Schema 4.0 调用当前用户的 Codex CLI，Actions 在本地失败或电脑离线时提供无本机凭据的确定性兜底。

### 成功标准

- 连续 30 次非外部故障运行中，定时任务成功率不低于 95%。
- 综合主榜和 AI 专题榜的日榜均固定输出 Top 3、周榜均默认输出 Top 7；候选不足时如实输出实际数量并给出质量说明。
- 两榜分别保存候选范围、排名和 Top N；同一仓库进入两榜时使用各自的排名序号。
- AI 分类对配置 Topics 使用精确匹配，并对仓库名、描述和 Topics 使用 token/phrase-aware 匹配；不得用 `"ai"` 子串命中 `rails`、`maintainer` 等无关词。
- 有完整基线时，Star/Fork/语言/链接等事实字段与 GitHub API 或快照一致率为 100%。
- 所有标为“本期新增 Star”的数字都能追溯到两个快照；无基线时不出现伪造增量。
- 运行时摘要的 JSON 可解析率为 100%，必填卡片字段完整率为 100%。
- Prompt 4.1 / Schema 4.0 的逐字段证据 ID 合法率、README SHA 一致率、许可证门禁通过率和冻结事实一致率均为 100%，无证据新增事实率为 0%。
- 榜内不得反复套用“近期升温”“聚焦”“值得关注”“赋能”等模板句；固定样本的标题、开场和亮点首词通过重复检查。
- 每个榜单生成 1 张封面、每个入榜项目生成 1 张 `1200×1600` PNG，数字与对应报告 JSON 一致率为 100%。
- 单次 GitHub Actions 运行在 20 分钟超时限制内完成，失败时返回非零退出码并留下可理解的日志。

## 2. 用户体验与功能

### 用户角色

- **内容运营者**：需要每天或每周快速得到可编辑、可核验的中文选题素材。
- **开发者/技术观察者**：希望了解近期增长项目，并能直接访问仓库验证。
- **项目维护者**：需要调整候选来源、过滤条件、榜单数量和排名权重，而不修改核心代码。

### 核心用户流程

```text
本地 CLI / GitHub Actions
        ↓
读取 config/hotspots.yaml
        ↓
Trending + Search 获取候选
        ↓
GitHub API 补全事实并过滤
        ↓
保存当日快照 → 与历史快照计算增量
        ↓
综合候选排名 + AI 可解释分类与独立排名
        ↓
清洗 README / metadata，安全缓存 Owner 头像
        ↓
确定性兜底与 7 个候选 / 可选 Codex Prompt 4.1 证据编辑
        ↓
双榜日报/周报 + 两份小红书卡片文案 + 数据质量说明
        ↓
Signal Broadsheet 封面与逐项目海报
        ↓
publish/current 标题、正文、审核稿与有序图片 → 人工审核发布
```

### 用户故事与验收条件

#### 故事 A：生成日榜

作为内容运营者，我希望运行一个命令生成当天的综合主榜 Top 3 和 AI 专题榜 Top 3，以便同时准备综合与 AI 日更内容。

验收条件：

- 命令为 `python -m github_hotspots.cli run --period daily`。
- 配置从 `config/hotspots.yaml` 读取，两榜默认 `daily_top_n: 3`，日榜使用 `lookback_days: 1`。
- 报告写入 `reports/daily/`，主 Markdown/JSON 包含两榜、统计窗口、数据质量和方法说明。
- `YYYY-MM-DD.xiaohongshu.md` 为综合主榜人工审核稿，`YYYY-MM-DD.ai.xiaohongshu.md` 为 AI 专题榜人工审核稿。
- 每个有效项目包含项目名、定位、语言、总 Star、本期新增 Star 或缺失说明、Fork、一句话价值、最多 5 条能力、核心亮点、适用人群、许可证状态和仓库链接；配套文字保留前置条件与限制。

#### 故事 B：生成周榜

作为内容运营者，我希望每周生成综合主榜 Top 7 和 AI 专题榜 Top 7，以便制作覆盖面更广、同时突出 AI 趋势的周报。

验收条件：

- 命令为 `python -m github_hotspots.cli run --period weekly`。
- 两榜默认 `weekly_top_n: 7`，周榜使用 `lookback_days: 7`。
- 报告写入 `reports/weekly/`。
- 周期依据实际快照日期计算，并在报告中显示开始和结束日期。

#### 故事 C：浏览综合主榜和 AI 专题榜

作为开发者或技术观察者，我希望同时查看全局热点和 AI 热点，并理解仓库为什么被归入 AI 专题。

验收条件：

- 综合主榜从全部合格候选独立排序；AI 专题榜只从 AI 匹配候选独立排序。
- 同一仓库允许同时进入两榜，且每个榜单分别计算和保存 `rank`。
- AI 分类先对配置 Topics 做精确匹配，再对仓库名、描述和 Topics 做 token/phrase-aware 匹配。
- 独立 token `ai`、`openai`、`llm` 及配置的机器学习短语可以命中；`rails`、`maintainer` 等仅包含字母 `ai` 的词不能命中。
- 分类规则、配置和固定正例/反例可审计，用回归测试防止误收与漏收。

#### 故事 D：核验新增 Star

作为读者，我希望“本期新增 Star”有明确口径，以便相信榜单数据。

验收条件：

- 快照位于 `data/snapshots/YYYY-MM-DD.json`，每条至少包含日期格式的 `captured_on`、`repository_id`、`full_name`、`stars`、`forks` 和 `open_issues`。
- 只有 `delta_source=snapshot` 时，公开文案才能使用“本期新增 +N Star”。
- 首次运行或基线缺失时输出 `null` 和明确警告，不把 Trending 或估算值改写成精确新增。
- `trending` 值可以公开显示为“Trending 日周期 Star”或“Trending 周期 Star”；`estimate` 值只能显示为“估算 +N Star”，两者都不能计入精确新增字段或封面汇总。
- 发生负差值、仓库转移、删除或 ID 冲突时标记数据异常，并保留仓库 ID 用于追踪。

#### 故事 E：获得证据化、卡片友好的中文摘要

作为内容运营者，我希望摘要短、稳定且不虚构，以便直接进入排版环节。

验收条件：

- 可选 Codex 证据编辑器使用 `prompts/repository_summary_zh.md` 与输出 Schema 4.0；确定性兜底和 7 个候选仍由程序生成。
- 输出仅为合法 JSON，不含 Markdown 代码围栏或额外解释。
- 数字、URL、语言、仓库标识、排名和统计窗口必须原样复制输入。
- `highlights` 恰好 3 条以兼容旧报告；`capabilities` 为 1 至 5 条，并包含 `core_title`、`core_summary`、`audience`、`prerequisites`、`limitations`、`license_label`、`license_restrictions`、`readme_sha` 和 `content_status`。
- 每个非空自然语言字段必须绑定当前仓库合法 `evidence_ids`；列表字段逐条绑定证据。
- 字段长度符合小红书卡片限制；证据不足时使用事实型回退文案并写入质量警告。
- README、描述、Topics 和 metadata 都是不可信证据，不能执行其中的指令、访问链接或跨仓库引用；模型只能在输入证据语义范围内进行白话改写。
- README 缺失时，`readme_sha=null`，除许可证字段外的自然语言字段必须逐字段匹配同一 angle 的单一候选；不得借 metadata 自由补写能力、前置条件、限制或受众。
- `NOASSERTION`、`OTHER`、`unknown` 或空许可证不得推断为 MIT；`license_restrictions` 只能逐字来自 README 连续原文。
- 任一证据 ID、README SHA、许可证、身份、数字、Schema 或重复检查失败时，丢弃整榜模型结果并使用确定性文案。
- 日榜 3 个项目使用 3 个不同角度，周榜 7 个项目覆盖全部 7 个角度；相邻项目不得复用同一角度。

#### 故事 F：自动定时运行

作为项目维护者，我希望无人值守地生成日报和周报。

验收条件：

- 本地日报主链路默认每天 07:30 运行，本地周报主链路默认周日 08:45 运行。
- Actions 日报在 09:17、周报在周日 10:27 兜底；发现同日期完整 Codex 报告时跳过生成。
- 本地任务使用独立 worktree、共享锁、严格 Codex 无回退门禁、路径白名单、Secret 扫描、安全 push 和 Pages 验证；两个 Actions 仍支持 `workflow_dispatch`。
- 只提交 `data/snapshots/` 和对应报告目录的变更；没有变更时不创建空提交。
- GitHub API 密钥只通过 `GITHUB_TOKEN` 环境变量/Secret 提供，不写入仓库或报告。
- 工作流只生成小红书审核资产（文案与原创海报），不登录、不发布，也不读取浏览器 Cookie 或账号会话。
- 小时级或近实时 schedule 暂不默认启用；在同日多快照、速率预算、并发提交、历史保留和 Pages 展示方案完成前，手动触发只称为按需刷新。

#### 故事 G：获得逐项目原创海报

作为内容运营者，我希望每个上榜项目都有一张可核验、可重复生成的竖版配图，以便在人工审核后制作小红书图文。

验收条件：

- 综合主榜和 AI 专题榜分别生成 1 张封面；每个入榜项目分别生成 1 张 `1200×1600` PNG。
- 图片由本地代码和项目内样式规则确定性渲染，不依赖图像模型，不下载参考帖图片、账号头像或第三方插画；项目名左侧可使用经过安全缓存的 GitHub Owner 头像。
- Owner 头像只接受受控 GitHub 头像域，限制重定向、下载体积、像素、尺寸和 Content-Type，使用 Pillow 去除 metadata 并重新编码为本地 PNG；失败时使用确定性占位图。
- 项目名、排名、语言、Star、Fork 和增长标签来自冻结后的报告字段，不能由模型重新绘制或改写。
- V4 项目卡固定采用原创 Signal Broadsheet：硬边报头、Owner 头像、rank tape、白话定位、紧凑 signal bar、五项能力轨道、跨栏核心亮点与底部受众。综合/AI 和 24H/7D 必须同时通过文字和颜色区分。
- 相同报告输入、渲染器/样式版本、字体文件和渲染环境下，布局、颜色选择和文件内容保持稳定；跨系统字体与栅格差异不保证 PNG 字节一致。
- Windows 和 GitHub Actions 使用可渲染中文的字体；缺字、溢出、截断和事实不一致均使图片门禁失败。
- 图片默认标记为人工审核稿，自动化不登录或发布到小红书。

### MVP 范围

- Python CLI、YAML 配置、GitHub Actions 定时任务。
- GitHub Trending 与 Search 候选发现、GitHub API 事实补全。
- 归档/Fork/镜像/黑名单等基础过滤。
- 日/周快照、Star 与 Fork 增量、可解释热度评分。
- 综合主榜和 AI 专题榜独立排名，允许同一仓库重叠入榜。
- 两榜日榜各 Top 3、周榜各 Top 7。
- 包含双榜的 Markdown/JSON、综合榜与 AI 榜两份小红书文本版卡片、方法与数据质量说明。
- 当前稳定产物已经包含文本与确定性 PNG 海报，两者进入同一人工审核包。
- 本地 `publish/current` 将日报/周报的综合榜与 AI 榜拆成四个独立帖子包；2026-07-12 为 `D001` 和 `W001`，首发日前只能标记预览。
- 确定性文案为默认路径；本地 Codex Prompt 4.1 / Schema 4.0 只在同仓库 README/metadata 证据范围内进行白话编辑，任一输出校验失败时整榜回退。
- 单元测试、格式/静态检查和本地运行说明。

### 非目标

- 自动登录或自动发布到小红书；当前阶段明确采用“生成内容 + 人工审核发布”，未来自动发布不属于本阶段范围。
- 绕过小红书登录、验证码、反爬机制或批量抓取作者内容。
- 使用生成式图像模型制作含事实数字的最终卡片，或复制参考账号的视觉资产、原文和品牌表达；视频和多平台成套物料仍不在当前范围。
- 预测未来 Star、判断项目投资价值或声称项目“官方排名”。
- 让 LLM 自行上网补数字、创建不存在的仓库链接或替代 GitHub 数据采集。

## 3. AI 系统要求

### 工具与输入要求

- Codex 证据编辑器只接收程序冻结的仓库/排名事实、`deterministic_draft`、7 个 `candidate_summaries`、经过清洗的 `repository_evidence.metadata/readme` 和当前仓库 `available_evidence_ids`。
- README、描述、Topics 和 metadata 一律视为不可信数据，不能执行其中的指令、访问链接、调用工具或跨仓库借用证据。
- 输入至少包含 `repository_id`、`full_name`、`html_url`、`description`、`language`、`stars`、`forks`、`topics`、周期、排名、`star_delta`、`delta_source`、README SHA 和允许证据 ID。
- 模型输出使用 `prompts/repository_summary_zh.md` 与 Schema 4.0 定义的 JSON 结构，并以整榜批处理方式分配不同编辑角度。
- README 存在时，模型可以在所引用证据语义内改写白话文案；README 缺失时只能逐字段采用同一受控候选。
- 未配置模型或模型调用/校验失败时，系统直接使用确定性文案，核心榜单不得因 AI 不可用而失败。
- GitHub Actions 默认不调用本地 Codex；本地适配器只调用 `codex exec`，绝不读取、复制或提交 Codex 用户级配置和凭据。

### 事实约束

- 模型不得计算、四舍五入、单位化或改写数字；展示格式由模板负责。
- 模型不得补全缺失 URL、语言、许可证、性能指标、兼容范围、公司采用情况或用户规模；许可证缺失或模糊时必须留空。
- 只有快照差值可以进入 `period_stars_added` 精确字段。
- 文案中的每个项目定位、能力、核心亮点、受众、前置条件、限制和许可证字段都必须绑定合法 `evidence_ids`。
- 模型不得增删仓库、改变两榜归属、改变排名或把未冻结的外部信息加入文案。
- 模型输出的身份、URL、语言、Star、Fork、排名、周期和增量字段必须与冻结输入完全一致；README SHA 和许可证原文必须通过专项回查。
- 输出包含 `data_quality`、`content_status` 和逐字段 `evidence_ids`，便于程序校验和人工抽查。

### 评估策略

建立至少 30 个仓库的固定样本集，覆盖描述缺失、语言缺失、README 很短、长项目名、中文项目、归档项目、无快照基线和负增量异常。每次调整提示词后检查：

- JSON 解析成功率：100%。
- 必填键和类型符合率：100%。
- 数字与 URL 精确复制率：100%。
- 自然语言字段合法证据覆盖率：100%。
- README 缺失分支的单一候选逐字段匹配率：100%。
- README SHA 与许可证门禁通过率：100%。
- 无依据事实新增率：0%。
- 长度限制通过率：100%。
- `highlights[3]` 与 `capabilities[1..5]` 条数符合率：100%。
- 禁用套话、开头句式和亮点首词的榜内重复检查通过率：100%。

## 4. 技术规格

### 架构与数据流

| 组件 | 责任 | 失败处理 |
| --- | --- | --- |
| 配置加载 | 读取时区、来源、过滤、榜单数量和权重 | 配置非法立即失败并指出键名 |
| 候选发现 | 合并 Trending 与 Search 结果 | 单一来源失败时降级，全部失败则退出 |
| GitHub 客户端 | 获取仓库事实、处理分页和限流 | 重试可恢复错误；限流时输出明确日志 |
| 快照存储 | 按日期保存最小事实集 | 原子写入；不得用半成品覆盖有效快照 |
| 增量计算 | 对齐 `repository_id` 后计算前后差值 | 无基线返回 `null`，不估造精确值 |
| AI 分类器 | Topics 精确匹配 + name/description/topics 的 token/phrase-aware 匹配 | 规则配置与固定正反例可审计；不得使用 `ai` 裸子串误收 |
| 排名器 | 综合主榜与 AI 专题榜分别归一化信号并计算可解释分数 | 保留各分量百分位和榜单内排名，确保稳定排序 |
| 证据采集与头像缓存 | 获取并清洗 README/metadata，安全缓存 Owner 头像并生成公开相对路径 | README 缺失时受控降级；头像失败时使用占位图 |
| 文案编辑 | 生成确定性兜底与 7 个候选；可选 Codex Prompt 4.1 / Schema 4.0 在证据内白话改写 | 任一 Schema、证据、README SHA、许可证或事实校验失败时整榜使用确定性结果 |
| 渲染器 | 生成 Markdown 和小红书文本 | 模板缺字段时失败，不静默吞错 |
| 海报渲染器（V4） | 为每榜生成封面和逐项目 `1200×1600` PNG，展示 Owner 头像、最多 5 条能力、核心亮点与适合谁 | 头像失败使用占位图；缺字体、文字溢出、事实不一致或保存失败时明确失败 |
| 发布包生成器 | 生成 Dxxx/Wxxx 标题、可粘贴正文、REVIEW、CHECKLIST、Manifest 和有序图片，轮转 current/archive | 路径穿越、图片损坏、尺寸/哈希或编辑元数据错误时拒绝生成 |
| 本地计划任务 | 当前用户的 Codex CLI、独立 worktree、锁、测试、严格门禁、安全提交/推送、Pages 与 publish 同步 | 任一环节失败不提交，Actions 稍后兜底 |

### 稳定数据契约

仓库事实使用内部字段：

```text
repository_id, full_name, html_url, description, language,
stars, forks, open_issues, watchers, topics,
created_at, updated_at, pushed_at,
daily_stars, weekly_stars,
trending_rank_daily, trending_rank_weekly, sources
```

排名结果额外包含：

```text
rank, score, star_delta, fork_delta,
delta_source, component_percentiles
```

报告 JSON 保留顶层 `repositories` 作为综合主榜，以兼容旧消费者；同时新增稳定的双榜结构：

```json
{
  "repositories": [],
  "boards": {
    "comprehensive": {
      "label": "综合主榜",
      "repositories": []
    },
    "ai": {
      "label": "AI 专题榜",
      "repositories": []
    }
  }
}
```

顶层 `repositories` 与 `boards.comprehensive.repositories` 内容一致。两榜的 `repositories` 分别保存独立排名；AI 榜为空时输出空数组和质量说明，不用综合榜补位。

图像输出接口在不破坏现有 JSON 消费者的前提下扩展：当期图片位于 `reports/<period>/assets/<stem>/`，每榜对应 1 张封面和按榜内排名排列的逐项目图片，并通过 Schema 2 `manifest.json` 提供可供 Pages 和人工审核读取的资产清单。清单记录 renderer 名称/版本、`style_version`、`source_report`、统计窗口、Top N，以及每项资产的榜单键、排名、仓库标识、相对路径和尺寸。

文案证据字段包含 `readme_sha`、`content_status` 和逐字段 `evidence_ids`；公开头像记录只保存报告根目录内的相对缓存路径，不保存本机绝对路径。Codex 输出 Schema 4.0 与报告/资产 Schema 是不同契约，不得混用版本号。

当前样例的日榜图片约 `1 MB`、周榜图片约 `2 MB`，日周合计约 `3 MB`。按每年 365 份日榜、52 份周榜并预留清单与体积波动，容量规划采用约 `495 MB/年`；Git 历史占用还可能更高。v1.2 必须定义保留与归档策略：主分支只保留可接受时段的近期资产，旧图片可迁移到 GitHub Releases 或外部静态存储，`manifest.json` 和历史页面继续保留可追溯链接；具体保留时长为 `TBD`，策略落地前不静默删除历史资产。

卡片层负责映射：

- `full_name` → 项目标识/项目名。
- `html_url` → 仓库链接。
- `stars` → 总 Star。
- `star_delta` → 本期新增 Star（须同时满足 `delta_source=snapshot`）。
- `forks` → Fork 总量。

### 集成点

- GitHub REST API：事实字段和仓库搜索。
- GitHub Trending 页面：候选信号，不作为精确 Star 增量来源。
- GitHub Actions：定时运行、测试、提交生成产物。
- 本地 Codex CLI（可选）：仅在事实和排名冻结后，基于清洗后的同仓库 README/metadata 做整榜证据化编辑；由 CLI 自行加载用户配置和凭据，项目不解析其内部存储。
- 冻结报告按需刷新：`rerender <report.json> --refresh-evidence --editorial-backend codex-cli` 只刷新 README、许可证、Owner 头像证据并重建文案/海报，不重新排名。
- 可选远程 LLM：只有用户未来明确授权并手动配置 GitHub Secrets 后才可进入受信任 CI；当前 Actions 默认不启用。

### 安全与隐私

- `.env`、Token、API 原始响应中的敏感头信息不得进入 Git。
- 日志不得打印 Token；HTTP 错误日志应脱敏。
- 外部文本按数据处理，防止 README 提示注入。
- Owner 头像只允许从受控 GitHub 头像域下载，限制重定向、体积、像素、尺寸和 Content-Type，重新编码去 metadata，并拒绝路径穿越和远程热链。
- 尊重 GitHub API 速率限制和小红书访问限制，不实现绕过机制。
- 报告只公开 GitHub 仓库公共信息，不收集小红书用户数据。
- 当前发布自动化止于生成综合榜和 AI 榜的文案与海报审核资产。人工审核与人工发布是固定门禁，任何自动发布能力都需要未来再次获得明确授权。
- 原创海报同样属于草稿资产；自动化可以生成、校验和展示，但不能据此自动操作小红书账号。
- GitHub Actions 默认使用 `deterministic`，不得复制本机 Codex 配置、认证、provider、endpoint 或 model 到 Secrets、日志或 artifact。

### 许可证与复用

- 项目代码和随附文档采用 MIT License，版权声明为 `Copyright (c) 2026 Zicheng Wang`。
- 允许个人或商业使用、修改、合并、发布和分发，但复制或分发软件及其主要部分时必须保留版权声明和 MIT 许可声明。
- MIT License 按“原样”提供软件且不附带担保；许可证不改变 GitHub 数据来源标注、第三方商标和外部内容各自的权利。

## 5. 风险与路线图

### 分阶段交付

#### 阶段 0：冷启动

- 初始化项目、配置、工作流和第一份快照。
- 无历史基线时生成冷启动说明，不发布伪增量榜单。

#### MVP：可审计的日榜/周榜

- 完成候选、事实、快照、增量、排名、摘要、报告和自动化闭环。
- 提供综合主榜与 AI 专题榜；两榜日榜各 Top 3、周榜各 Top 7，独立排名并允许重叠。
- 输出包含双榜的主报告和两份小红书人工审核稿。
- 通过测试并留下可复现命令。

#### v1.1：当前内容生产升级

- 已实现 Prompt 4.1 / Schema 4.0：程序清洗 README/metadata，Codex 可在逐字段证据边界内写白话内容，确定性兜底仍保持默认可用。
- 已增加每榜封面和逐项目 `1200×1600` V4 PNG，采用参考图信息架构、安全 Owner 头像缓存和确定性占位图。
- 已把 Schema 2 图片清单接入报告、Pages 预览/下载和日周工作流，并完成中文字体与字形门禁；跨系统 PNG 字节不作为一致性承诺。
- 已增加本地 `codex exec` Prompt 4.1 / Schema 4.0 证据编辑适配器，并覆盖 README 缺失、非法证据 ID、README SHA/许可证/事实漂移和整榜回退；默认 CI 仍不启用。
- 增加人工审核状态、选题排除原因和历史回看。
- 增加提示词版本、模型成本、延迟和 JSON 成功率监控。

#### v1.2：运行与质量增强

- 增加计划运行失败通知、图像回归样本、链接检查和内容重复率趋势。
- 完善同日手动重跑策略、资产保留与 Pages 历史导航。
- 根据约 `495 MB/年` 的图片增长基线，确定主分支保留时长、旧资产归档位置、链接迁移和恢复流程。
- 评估小时级快照的数据模型和 API 预算，但不默认启用近实时提交。

#### v2.0：多渠道与个性化

- 增加技术领域/语言分榜、去重和长期趋势。
- 支持多平台草稿导出；自动发布不在当前规划承诺内，只有用户未来再次明确授权且平台允许时才单独立项。
- 增加网页仪表盘、订阅和历史对比，不默认公开用户私有配置。

### 主要风险与缓解

| 风险 | 影响 | 缓解措施 |
| --- | --- | --- |
| 首次运行无基线 | 不能精确计算新增 Star | 明确冷启动，至少积累两个快照后再标精确新增 |
| Trending 页面结构变化 | 候选数量下降 | Search 作为独立来源；解析测试与降级日志 |
| GitHub API 限流/故障 | 报告延迟或字段缺失 | Token、重试、缓存、超时和非零退出码 |
| 同日重复运行覆盖快照 | 周期口径失真 | 保留 `captured_on`，定义同日覆盖/版本策略并原子写入 |
| Codex 输出越过证据边界或遭 README 提示注入 | 内容失真 | 不可信输入隔离、Schema 4.0、逐字段证据、README SHA/许可证/冻结事实回查和整榜确定性回退 |
| 小红书参考内容变化 | 版式漂移 | 把字段契约固化在本仓库，不依赖页面实时抓取 |
| 高频更新放大限流和提交冲突 | 数据不稳定、仓库历史膨胀 | 保持日/周 schedule；近实时单独设计时间戳快照、预算、保留和并发策略 |
| 海报中文字或数字错误 | 发布资产不可用 | 确定性渲染、中文字体门禁、尺寸/溢出测试、与报告 JSON 回查 |
| Owner 头像恶意媒体、热链或路径越界 | 构建或发布风险 | 受控头像域、重定向/体积/像素/格式限制、重新编码去 metadata、本地相对路径和失败占位图 |
| PNG 长期累积 | 仓库和 Git 历史持续膨胀 | 以约 `495 MB/年` 作为容量规划基线，在 v1.2 落地主分支保留与旧资产归档策略 |

### 最终验收清单

- [x] `python -m pytest` 通过。
- [ ] 日榜和周榜 CLI 均能在干净环境运行。
- [x] `config/hotspots.yaml` 能控制 Top N、过滤和排名权重。
- [x] 快照可重读，增量可由两个快照独立复算。
- [x] 综合主榜与 AI 专题榜分别独立排名，允许同一仓库重叠入榜。
- [x] 两榜日榜各 Top 3、周榜各 Top 7；候选不足时有明确质量说明。
- [x] AI Topics 精确匹配和 token/phrase-aware 正反例测试通过，不发生 `ai` 子串误收。
- [x] 每张卡片包含白话定位、兼容 `highlights[3]`、最多 5 条能力、核心亮点、适合人群和许可证状态；配套文字包含前置条件与限制。
- [x] 所有精确新增 Star 均来自快照；无基线时有清晰警告。
- [x] 摘要 JSON 可解析、字段长度合规、数字和链接未被改写。
- [x] 榜内模板句、开头句式和禁用套话检查通过。
- [x] Codex Prompt 4.1 / Schema 4.0 输出通过逐字段证据、README SHA、许可证和冻结事实校验；README 缺失时只允许同一受控候选，失败时整榜回退。
- [x] Owner 头像经过安全缓存和重新编码，失败时 V4 海报使用确定性占位图。
- [ ] GitHub Actions 的时区、计划、测试和提交范围正确。
- [x] daily/weekly 均支持 Actions 手动触发，文档未把按需刷新描述为实时事件流。
- [x] 综合榜和 AI 榜两份小红书稿均已生成，且没有自动登录或发布步骤。
- [x] 每榜封面与逐项目 `1200×1600` PNG 数量、尺寸、中文字体和事实字段全部通过门禁。
- [x] README/方法说明明确声明本榜单不是 GitHub 官方排名。
- [x] 根目录 MIT `LICENSE` 存在，README 说明复用时需保留版权和许可声明。
