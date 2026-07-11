# GitHub Hotspots 完整项目规划

> 文档状态：v0.2（关键产品决策已确认）
> 基准日期：2026-07-11
> 适用范围：公开 GitHub 仓库、自动化日榜/周榜、中文内容素材、GitHub Pages 项目页面
> 决策原则：已确认决策按本文执行；仍未得到用户确认的未来能力继续标记为 `TBD`，不得据此扩大外部发布或凭据权限。

## 1. Executive Summary

### Problem Statement

人工发现 GitHub 热点、核对 Star 增量、整理中文亮点并维护日榜/周榜，存在耗时、口径不一致、数据不可追溯和内容生成失真的问题。当前仓库已经具备基础采集、快照、排名、报告、公开仓库和 GitHub Pages 发布闭环；下一阶段重点是稳定双榜运营、积累真实 7 日基线、完善质量监控和文件化人工审核流程。

### Proposed Solution

将现有 Python 3.12 流水线建设为一个公开、可复现、可审计的 GitHub 热点产品：由 GitHub Actions 定时采集公开数据并生成日榜/周榜，以本地快照计算真实增量，以事实约束摘要器生成中文素材，再通过 GitHub Pages 展示历史榜单、方法说明和项目状态。内容进入外部平台前保留人工审核；AI 是可选增强层，失败时必须回退到确定性规则摘要，不得阻断核心榜单。

### Current Baseline

- 产品范围已锁定为“综合主榜 + AI 专题榜”：两榜日榜各 Top 3、周榜各 Top 7，分别排名且允许同一仓库重叠入榜。
- 已有 GitHub Trending、GitHub REST Search、GitHub API 元数据补全、日快照、六因子排序和降级逻辑。
- 已有包含双榜的 Markdown/JSON、综合榜与 AI 榜两份小红书审核稿，以及每日/每周 GitHub Actions。
- 当前 Git 分支为 `main`；公开远程仓库已创建，静态 GitHub Pages 与正式发布工作流已实现并通过首次线上部署验证。
- 当前摘要器为确定性规则实现；本地 Codex 适配器尚未验证可行性。

### Success Criteria

- 在连续 30 次非外部故障的计划运行中，日榜和周榜工作流成功率均达到 `>= 95%`。
- 所有公开展示的仓库 URL、总 Star、Fork、语言和精确增量字段与 GitHub API/对应快照一致率达到 `100%`。
- 每次成功运行后，报告在计划触发时间后的 `30 分钟`内写入仓库，并在 `15 分钟`内完成 Pages 部署。
- 小红书草稿从生成到可人工发布的中位整理时间降至 `<= 15 分钟`，且发布前人工审核覆盖率为 `100%`。
- 综合主榜和 AI 专题榜分别达到日榜 Top 3、周榜 Top 7 的数量契约；候选不足时不得用另一榜单补位。
- AI/规则摘要的 JSON 可解析率、必填字段完整率和数字/URL 原样复制率均为 `100%`，无证据新增事实率为 `0%`。

### Confirmed and Open Decisions

| 决策 | 状态 | 已采用方案 | 影响 |
| --- | --- | --- | --- |
| 热点范围 | `已确认` | 同时提供“综合主榜 + AI 专题榜”；综合榜覆盖全部合格候选，AI 榜筛选后独立排名，允许重叠 | 配置结构、报告 Schema、Pages 展示、测试样本 |
| 小红书发布方式 | `已确认` | 当前仅生成综合榜和 AI 榜两份审核稿，由用户人工审核和发布；不自动登录或发布 | 自动发布不在当前阶段，未来如需建设必须重新明确授权 |
| 开源许可证 | `已确认` | 使用 MIT License，版权声明为 `Copyright (c) 2026 Zicheng Wang` | 允许商用、修改与分发；复制或分发时保留版权和许可声明 |
| Codex Chrome Extension | `已安装并核验` | 2026-07-11 已完成只读连接验证；不在仓库记录标签页、登录态或其他浏览器隐私数据 | 浏览器能力只作辅助，不成为核心流水线依赖 |
| 本地 Codex 能力接入 | `原则已确认，代码待排期` | 仅通过受支持的 `codex exec` 建立可选适配器；禁止读取、复制或提交 Codex 凭据文件 | 摘要 Provider 接口、本地任务调度、错误回退策略 |
| GitHub Pages 技术方案 | `已上线` | 使用仓库内 JSON 生成纯静态站点，由 Actions 部署；首版不引入数据库 | 持续验证报告更新触发的数据重建链路 |
| 公开仓库名称与 Pages 域名 | `已确认` | 仓库为 `wzgig/github-hotspots`，Pages 使用 `wzgig.github.io/github-hotspots/` | README 徽章、链接、发布说明、SEO 元数据 |

## 2. User Experience & Functionality

### User Personas

- **内容运营者**：每天或每周需要得到可核验、可编辑、可直接进入排版环节的中文选题和文案。
- **开发者/技术观察者**：希望快速查看近期增长项目、理解入榜原因，并能点击仓库链接核验。
- **项目维护者**：需要通过配置调整范围、过滤器、榜单数量和权重，并能定位定时任务故障。
- **公开页面访客**：希望在手机或桌面浏览器中查看最新榜单、历史榜单、方法说明和数据口径。

### Primary User Flow

```text
计划触发/手动触发
  -> 读取配置与榜单范围
  -> Trending + Search 获取候选
  -> GitHub API 补全、去重与过滤
  -> 保存快照并匹配 1 日/7 日基线
  -> 综合榜/专题榜分别评分
  -> 规则摘要或事实约束 AI 摘要
  -> 输出 JSON + Markdown + 社交文案
  -> 自动测试与数据质量门禁
  -> 提交 main 并部署 GitHub Pages
  -> 用户审核社交内容
  -> 人工发布并记录反馈
```

### User Stories and Acceptance Criteria

#### Story A — 生成可信的日榜

As a 内容运营者, I want to 每天得到综合主榜 Top 3 和 AI 专题榜 Top 3 so that 我能快速完成全局与 AI 两类当天选题。

Acceptance Criteria:

- `python -m github_hotspots.cli run --period daily` 在有效配置下返回退出码 `0`。
- 主 Markdown/JSON 同时包含两榜；综合榜写入 `YYYY-MM-DD.xiaohongshu.md`，AI 榜写入 `YYYY-MM-DD.ai.xiaohongshu.md`。
- 每个入榜项目至少包含仓库标识、仓库链接、语言、总 Star、Fork、增量口径、入榜分数和数据质量信息。
- 仅当 `delta_source=snapshot` 时使用“本期新增”表述；无 1 日基线时明确显示“待积累”。
- 同一输入、配置和日期重复运行时，排名顺序保持确定性。

#### Story B — 生成可信的周榜

As a 内容运营者, I want to 每周得到综合主榜 Top 7 和 AI 专题榜 Top 7 so that 我能制作覆盖面更广且突出 AI 趋势的周报。

Acceptance Criteria:

- `python -m github_hotspots.cli run --period weekly` 可独立运行。
- 两榜默认分别输出 Top 7；候选不足时如实输出实际数量并给出质量警告。
- 报告显示实际开始/结束快照日期和 7 日基线可用性。
- 无完整 7 日基线时，不将 Trending 周期 Star 或估算值伪装为精确净增量。

#### Story C — 浏览综合主榜与 AI 专题榜

As a 技术观察者, I want to 在综合热点之外查看 AI 专题 so that 我既能观察全局，又不会错过高增长 AI 项目。

Acceptance Criteria:

- 双榜范围已经用户确认。综合主榜不强制限定技术领域；AI 专题榜使用独立的分类规则、Top N 和排名结果。
- 同一仓库可同时进入两榜，但页面和 JSON 必须显示其榜单范围及独立排名，不能复用排名序号。
- AI 分类先对配置 Topics 做精确匹配，再对仓库名、描述和 Topics 做 token/phrase-aware 匹配；独立 token `ai`、`openai`、`llm` 及配置短语可命中，但 `rails`、`maintainer` 等只包含 `ai` 子串的词不得命中。
- AI 分类只使用 topics、name、description 与显式配置规则；规则和固定正反例必须可审计，并允许维护排除名单。

#### Story D — 在 GitHub Pages 查看项目页面

As a 公开页面访客, I want to 浏览最新榜单和历史记录 so that 我无需克隆仓库也能理解结果和方法。

Acceptance Criteria:

- Pages 首页包含项目定位、最新日榜、最新周榜、数据更新时间和方法免责声明。
- 页面分别展示综合主榜和独立的 AI 数据雷达，两者均提供今日日榜与本周周榜。
- 提供历史日期/周次导航、项目仓库链接、数据口径页、项目日志和运行状态入口。
- 页面适配宽度 `360px` 的移动端和常见桌面尺寸；关键文本无需横向滚动。
- 页面只读取已提交的公开产物，不暴露 Token、用户本机路径、私有配置或原始认证响应。
- 每次 main 的用户可见变更都经过构建验证；部署失败不得被报告为“已上线”。

#### Story E — 审核小红书发布包

As a 内容运营者, I want to 在发布前查看事实、文案和风险提示 so that 我能避免错误内容直接对外发布。

Acceptance Criteria:

- 当前发布策略已经确认：系统只生成审核包，由用户人工审核和发布；不自动登录或发布到小红书。
- 审核包包含候选正文、标题、标签建议、数据更新时间、仓库链接和数据质量警告。
- 精确数字可回溯到当期 JSON/快照；修改后的文案不得覆盖原始数据证据。
- 自动生成文件一律视为 `draft`；`approved`、`rejected` 和最终发布动作由人工流程管理。
- 自动发布不属于当前阶段。未来若重新立项，未标记 `approved` 的内容也不得进入发布适配器。

#### Story F — 安全地使用本地 Codex 增强摘要

As a 项目维护者, I want to 可选地调用本地 Codex 能力 so that 我能获得更自然的中文表达而不依赖 OpenAI 官网 API Key。

Acceptance Criteria:

- 在实现前验证本机是否存在受支持、可脚本化、可非交互运行的 Codex CLI 或明确本地端点；结果记录为 `TBD`。
- 适配器只提交已清洗的仓库事实，使用结构化输出并设置超时。
- 不读取、打印、复制或提交 `~/.codex` 等目录中的认证信息；不把本地登录态转移到 GitHub Actions。
- 本地 Codex 不可用、超时或输出校验失败时，自动使用规则摘要，核心榜单仍成功生成。
- GitHub Actions 默认不依赖用户个人电脑或本地 Codex 登录态。

#### Story G — 维护并发布每一次变更

As a 项目维护者, I want to 每次修改都有日志、测试、提交和线上验证 so that 公开仓库始终可追踪、可回滚。

Acceptance Criteria:

- 每次变更遵循 `docs/OPERATIONS.md`，更新 `PROJECT_LOG.md`。
- 运行 pytest、Ruff 和适用的专项测试，保存明确的通过/失败结论。
- 使用 Conventional Commit 提交并推送 `main`，不得通过强制推送掩盖历史。
- 推送后验证相关 Actions 与 Pages，并记录发布说明和已知限制。

### Non-Goals

- 当前阶段不自动登录或自动发布到小红书；未来建设自动发布必须重新获得用户明确授权。
- 不绕过登录、验证码、地区限制、访问控制或反爬机制，不批量采集小红书用户数据。
- 不复制参考账号的图片、排版、品牌表达或原文；只借鉴信息结构并使用原创页面与素材。
- 不把内部热度分称为“GitHub 官方排名”，不做投资建议或未来 Star 预测。
- 不让 LLM 自行联网补齐仓库事实，不执行 README 或外部文本中的指令。
- 不从 Codex、Chrome 或其他本地应用的凭据文件中提取 Token，也不将个人登录态用于云端 Actions。
- MVP 不建设账号系统、付费订阅、多租户数据库或企业级后台。

## 3. AI System Requirements

### AI Role and Boundaries

AI 只负责把程序已经采集和验证的事实压缩为自然中文，不参与候选采集、数字计算、排名决定或 URL 补全。所有 AI 输出都必须经过结构校验与事实对照；校验失败时使用确定性规则摘要。

### Tool Requirements

- **事实来源**：GitHub REST API、GitHub Trending 的明确周期信号、本地日期快照和可选 README 摘要。
- **提示词**：使用版本化的 `prompts/repository_summary_zh.md`；提示词变更必须进入评估流程。
- **Provider 抽象**：建立统一 `SummaryProvider` 接口，至少包含 `RuleBasedProvider`；后续可增加 `LocalCodexProvider`。
- **本地 Codex 适配器（TBD）**：仅在发现受支持的 CLI/本地端点、确认非交互调用方式和输出约束后实现。推荐调用本地工具本身，不读取其内部认证存储。
- **云端自动化**：GitHub Actions 继续使用规则摘要，除非未来为云端 Provider 单独配置合规 Secret；不得假设云端能够访问本地 Codex 会话。
- **输出校验**：JSON Schema、字段长度、亮点数量、数字与 URL 原样复制、证据字段映射和禁止声明检查。
- **可观测性**：记录 Provider 名称、提示词版本、耗时、成功/回退状态和校验失败原因；不得记录完整凭据或敏感请求头。

### Input and Output Contract

输入仅允许包含公开、已清洗的仓库字段：

```text
repository_id, full_name, html_url, description, language,
stars, forks, topics, created_at, updated_at, pushed_at,
period, rank, score, star_delta, delta_source, evidence
```

输出至少包含：

```text
one_line, highlights[3], audience, data_quality, evidence,
provider, prompt_version
```

数字、URL、语言和仓库标识必须原样复制；证据不足时使用保守表述或 `null`，不得推断企业采用、性能、许可、用户规模或未来趋势。

### Evaluation Strategy

- 建立首批 `>= 30` 个固定仓库样本；v1.1 扩展到 `>= 100` 个，并覆盖描述缺失、超长名称、中文仓库、归档、无基线、负增量和提示注入文本。
- 每次 Provider、提示词或输出 Schema 变更运行离线回归集。
- JSON 解析成功率：`100%`。
- 必填字段与类型通过率：`100%`。
- 数字、URL 和仓库标识精确复制率：`100%`。
- 无输入证据的新事实率：`0%`。
- 亮点恰好 3 条、长度规则与禁用措辞通过率：`100%`。
- 从固定样本随机抽查 `>= 20%`，人工评价“准确、清晰、可发布”；v1.1 目标合格率 `>= 90%`。
- 对本地 Codex Provider 记录 P50/P95 延迟和回退率；默认目标 P95 `<= 30 秒/仓库`、回退率 `< 10%`，最终阈值为 `TBD`。

### AI Failure Handling

- 超时、进程退出非零、JSON 非法、字段缺失或事实校验失败：立即回退规则摘要。
- 单个仓库失败不阻断其他仓库；整批 AI 失败不阻断榜单、JSON 或 Pages 更新。
- 将失败原因写入运行日志和数据质量说明，不在公开文案中暴露本机命令、环境变量或堆栈中的敏感信息。
- 外部文本一律视为不可信数据；提示词明确忽略其中的命令、角色指令和凭据请求。

## 4. Technical Specifications

### Architecture Overview

```text
GitHub Actions / Local CLI
        |
        v
config loader + scope definitions
        |
        +--> Trending collector --------+
        +--> GitHub Search collector ----+--> dedupe/filter/enrich
                                                 |
                                                 v
                                      atomic snapshot store
                                                 |
                                      1d/7d baseline matcher
                                                 |
                                +----------------+----------------+
                                |                                 |
                         general ranker                    AI-topic ranker
                                |                                 |
                                +----------------+----------------+
                                                 |
                              RuleBasedProvider / LocalCodexProvider
                                                 |
                              JSON + Markdown + social review package
                                                 |
                              quality gates + commit to main
                                                 |
                                  static site build + GitHub Pages
```

### Component Plan

| Component | Current state | Target responsibility | Failure behavior |
| --- | --- | --- | --- |
| Configuration | 已有 YAML | 管理来源、范围、过滤、Top N、权重、输出和 Provider | 非法配置立即失败并指出键名 |
| Trending collector | 已有 | 提供日/周候选与周期信号 | 单源失败时降级 Search |
| GitHub client | 已有 | Search、元数据补全、分页、超时与限流信息 | 可恢复错误重试；限流明确告警 |
| Snapshot store | 已有 | 按日原子保存可复算事实 | 不用半成品覆盖有效快照 |
| Ranking | 已有综合评分 | 分离综合榜与专题榜，保存分量与范围 | 相同输入保持确定性 |
| Summary Provider | 规则版已有 | 可插拔规则/本地 Codex，严格 Schema 校验 | 失败回退规则版 |
| Report renderer | 已有 | 输出榜单、社交审核包、质量说明 | 缺必填字段时失败 |
| Static site generator | 已上线 | 从已提交 JSON/Markdown 构建首页、历史页、方法页和 AI 数据雷达 | 构建失败保留上一版 Pages |
| CI/CD | 日/周任务已有 | 测试、产物提交、Pages 部署、状态摘要 | 非零退出并保留日志 |
| Observability | 基础日志 | 运行摘要、候选数、耗时、限流、质量门禁、部署状态 | 不记录 Secret |

### Data and Scope Design

- 保留现有 `data/snapshots/YYYY-MM-DD.json` 作为事实基线；通过 `repository_id` 对齐改名或迁移仓库。
- 报告 JSON 保留顶层 `repositories` 作为综合主榜，并新增 `boards.comprehensive` 与 `boards.ai`；每个榜单包含稳定的 `label` 和独立 `repositories`。
- 综合主榜和 AI 专题榜共享事实快照，但分别配置 Top N 和排名结果；AI 榜使用 Topics 精确匹配及 name/description/topics 的 token/phrase-aware 匹配。
- 保持现有 `reports/daily/YYYY-MM-DD.*`、`reports/weekly/YYYY-Www.*` 可读，旧 `*.xiaohongshu.md` 继续表示综合主榜；新增 `*.ai.xiaohongshu.md` 表示 AI 专题榜，避免破坏旧链接。
- Pages 只消费版本化、通过校验的报告 JSON；不直接在浏览器端调用 GitHub API。
- 对同日重跑定义明确覆盖策略，并保留 `generated_at`、数据窗口和源状态；不声称日期快照具有秒级精度。

### Integration Points

#### GitHub

- GitHub REST API：公开仓库搜索与事实字段；凭据来自 `GITHUB_TOKEN` 环境变量。
- GitHub Trending：候选信号，不作为官方 API，也不替代快照净增量。
- GitHub Actions：测试、日榜/周榜生成、自动提交和 Pages 部署。
- GitHub Pages：纯静态公开页面；建议用独立部署工作流并在构建前校验报告 Schema。
- GitHub Releases：里程碑版本发布说明；普通变更记录在 `PROJECT_LOG.md` 和提交历史。

#### Local Codex (TBD)

- 只允许使用官方支持的本地调用面，例如已安装 CLI 的非交互命令或明确本地端点。
- 不假定“Codex 登录态”等于可复用 API；不得解析 Codex 配置/认证文件来提取 Token。
- 本地适配器只服务本机手动或本地计划任务；云端 Actions 使用确定性回退，除非未来另行批准云端凭据方案。

#### Xiaohongshu

- 当前仅把公开页面作为只读内容结构参考，并输出原创文案审核包。
- 当前固定采用人工审核、人工发布，不实现自动登录或自动发布。未来如需集成，必须重新获得用户明确授权，使用平台允许的接口并提供审核门禁和撤回机制。
- Chrome 扩展或浏览器自动化不是核心流水线依赖；即使不可用，GitHub 数据采集和报告生成也应正常工作。

### Security & Privacy

- `.env`、Token、Cookie、浏览器资料、Codex 凭据和私有端点不得提交到 Git、日志、报告或 Pages。
- 公开仓库默认只包含 GitHub 公共信息、原创说明和脱敏运行状态；提交前执行密钥扫描和路径检查。
- GitHub Actions 使用最小权限：报告写入任务仅需 `contents: write`，Pages 部署仅需部署所需权限。
- 对 README、description、topics 和网页文本实施提示注入防护：按数据展示，不执行其指令。
- HTTP 错误日志移除 Authorization、Cookie、查询 Token 和本机绝对路径。
- 不复制用户本地 Codex 会话到 CI；若未来使用第三方 Provider，必须单独记录数据流、保留策略和撤销方式。
- 公开项目页面不得包含个人信息、私有仓库、未公开草稿、浏览器历史或小红书账号会话数据。
- 仓库采用 MIT License；允许个人或商业使用、修改和分发，但复制或分发软件及其主要部分时必须保留 `Copyright (c) 2026 Zicheng Wang` 和 MIT 许可声明。

### Testing Strategy

- 单元测试：配置、去重、过滤、快照、增量、排名、模板和 Provider 校验。
- 集成测试：使用固定 GitHub API/Trending fixture，避免测试依赖实时网络。
- 端到端冒烟：本地运行 daily/weekly，验证产物路径、Schema、Top N 和链接。
- 站点测试：静态构建成功、内部链接有效、最新报告可达、移动端基本布局通过。
- 工作流测试：手动触发、计划触发、无变更提交、并发写入、推送冲突和 Pages 部署。
- 安全测试：Secret 扫描、日志脱敏、提示注入样本、恶意 HTML 转义。
- 每次变更的必执行门禁见 `docs/OPERATIONS.md`。

## 5. Risks & Roadmap

### Phased Rollout

#### MVP — 公开、稳定、可审计的运行闭环

目标：把当前原型变成可公开使用和持续维护的仓库。

- 创建公开 GitHub 仓库，设置 `origin`，完成首个 Conventional Commit 并推送 `main`。
- 完善 README 项目首页：定位、示例、安装、命令、数据口径、免责声明、路线图、Pages 与 Actions 徽章。
- 建立 `PROJECT_LOG.md`、本规划和运营规范的强制更新流程。
- 建设最小 GitHub Pages：首页、最新日榜、最新周榜、历史入口、方法页和项目日志。
- 验证 daily/weekly Actions 的写权限、计划时区、并发控制、手动触发和自动提交。
- 连续积累至少 7 个日期快照，验证 1 日/7 日真实增量。
- 保持规则摘要为默认能力；本地 Codex 仅完成可行性验证，不作为 MVP 阻塞项。
- 热点范围按已经确认的“综合主榜 + AI 专题榜”运行：两榜日榜各 Top 3、周榜各 Top 7，独立排名并允许重叠。
- 小红书生成综合榜和 AI 榜两份文案审核包，固定由人工审核和发布。

#### v1.1 — 内容生产与项目页面增强

目标：降低人工排版成本，提升历史浏览、审核和质量监控能力。

- 完善综合榜/AI 专题榜的分类评估、历史对比和 Pages 交互。
- 生成原创 3:4 封面与项目卡片，提供主题、字体、色彩和水印配置。
- 引入文件化审核状态和发布清单，支持草稿、批准、拒绝与修改记录。
- 完成 `SummaryProvider` 抽象；在可行时增加受支持的 `LocalCodexProvider`。
- 建立固定 AI 评估集、提示词版本、Provider 延迟与回退监控。
- Pages 增加历史筛选、项目趋势、榜单方法、运行健康状态和响应式优化。
- 增加失败通知（GitHub Issue、邮件或其他渠道为 `TBD`）。

#### v2.0 — 多专题、趋势洞察与受控分发

目标：从单一榜单生成器发展为可扩展的开源趋势内容系统。

- 增加语言榜、领域榜、自定义关键词榜和长期趋势，但保持各榜口径独立。
- 建设跨周期去重、连续上榜、增长曲线和历史对比。
- 提供订阅/Feed、可下载数据集和多平台草稿导出。
- 小红书或其他平台自动发布不属于当前阶段；未来只有在用户再次明确授权、平台规则允许、具备审核门禁和撤回机制后才可单独立项。
- 可选建设轻量管理界面；账号、数据库和多租户是否需要为 `TBD`。
- 建立版本化公共数据 Schema 和兼容策略。

### Milestones and Task Dependencies

| ID | Milestone / task | Depends on | Exit criteria | Status |
| --- | --- | --- | --- | --- |
| M0 | 公开仓库初始化与首次推送 | GitHub 登录、仓库名确认 | `origin` 可访问，`main` 与本地一致 | 已完成 |
| M1 | 仓库级文档与运营规范 | M0 可并行起草 | README、PROJECT_LOG、PROJECT_PLAN、OPERATIONS 齐全 | 已完成 |
| M2 | Actions 首次线上验证 | M0、仓库 Actions 写权限 | daily/weekly 手动运行成功并产生可追踪产物 | 待执行 |
| M3 | 最小 Pages 上线 | M0、站点方案确认 | 公网 URL 可访问最新日/周榜及方法说明 | 已完成 |
| M4 | 7 日快照基线验收 | M2、连续运行 | 至少 7 个有效日期快照，周增量可复算 | 待积累 |
| M5 | 双榜范围实现 | 热点范围已确认、M3 | 综合榜/AI 榜独立配置、测试、页面与报告 | 已完成 |
| M6 | 原创图片与审核包 | 设计规范、M3 | 3:4 图片可重复渲染，发布前有审核状态 | v1.1 |
| M7 | 本地 Codex Provider | 支持方式验证、评估集 | 结构化输出通过门禁，失败自动回退 | `TBD` |
| M8 | 运行监控与通知 | M2、通知渠道确认 | 失败可在目标时限内被发现并定位 | v1.1 |
| M9 | 多专题与趋势分析 | M4、M5、Schema 版本化 | 多榜可复算，历史页面和导出稳定 | v2.0 |
| M10 | 受控平台分发 | 未来再次明确授权、平台允许接口、M6 | 仅 approved 内容发布，可审计、可停止 | 非当前阶段 |

Critical path:

```text
M0 -> M2 -> M4 -------> M9
  \-> M3 -> M5 ------> M9
          \-> M6 -----> M10
M1 ----------------^
M7 可在 M4 后并行，但不得阻塞核心榜单
```

### Quantitative KPIs

| KPI | MVP target | v1.1 target | Measurement source | Review cadence |
| --- | --- | --- | --- | --- |
| 计划任务成功率 | `>= 95%` / 30 次 | `>= 98%` / 90 次 | GitHub Actions runs | 每周 |
| 报告准时率 | 触发后 30 分钟内 `>= 95%` | `>= 98%` | 运行与提交时间 | 每周 |
| Pages 部署时延 | 提交后 `<= 15 分钟` | P95 `<= 10 分钟` | Pages deployment | 每次发布 |
| 精确字段一致率 | `100%` | `100%` | JSON/快照/API 对照 | 每次运行抽检 |
| 精确增量可追溯率 | `100%` | `100%` | 两期快照对照 | 每次运行 |
| 无依据事实新增率 | `0%` | `0%` | 固定评估集 + 人工抽检 | 每次提示词变更 |
| 摘要结构通过率 | `100%` | `100%` | Schema validator | 每次运行 |
| 人工发布前审核率 | `100%` | `100%` | 审核状态 | 每次发布 |
| 草稿整理时间 | 中位数 `<= 15 分钟` | 中位数 `<= 10 分钟` | 运营记录 | 每月 |
| 单次运行耗时 | `< 20 分钟` | P95 `< 10 分钟` | Actions duration | 每周 |
| 站点可访问性 | 最新页面人工可达 | Lighthouse Accessibility `>= 90` | 自动/人工页面检查 | 每次页面改动 |
| 测试稳定性 | main 上失败测试为 `0` | 分支覆盖率 `>= 85%`（建议） | pytest/coverage | 每次变更 |

### Technical Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation / fallback |
| --- | --- | --- | --- |
| GitHub API 限流或故障 | 字段缺失、任务失败 | 中 | 使用 Actions Token、缓存、超时、有限重试；不得以旧数据伪装新数据 |
| Trending HTML 结构变化 | 候选减少或解析错误 | 高 | fixture 回归、Search 独立来源、清晰降级警告 |
| 快照只覆盖当日候选 | 部分项目缺少基线，产生幸存者偏差 | 中 | 扩大稳定观察池；在质量字段中披露基线覆盖率 |
| 同日重跑覆盖历史 | 周期口径失真 | 中 | 原子写入、明确覆盖策略、保留生成时间和修正日志 |
| Actions bot 与人工 push 冲突 | 自动提交失败 | 中 | 并发组、push 前同步、失败后重新运行；不强推 main |
| `[skip ci]` 影响 Pages 触发 | 页面不更新 | 中 | Pages 使用独立 `workflow_run`/手动触发或显式部署，不依赖被跳过的 push 流程 |
| AI 摘要幻觉或提示注入 | 对外内容失真 | 中 | 不可信输入隔离、Schema/事实校验、规则回退、人工审核 |
| 本地 Codex 无受支持 API | 适配器不可实现或不稳定 | 高 | 标记 `TBD`；只用支持的 CLI/端点，核心云端流程保持无 AI 依赖 |
| 凭据进入公开仓库 | 严重安全事故 | 低/高影响 | `.gitignore`、Secret 扫描、最小权限、提交前检查、立即轮换与清理流程 |
| Pages 构建或链接失效 | 公开入口不可用 | 中 | 构建门禁、链接检查、保留上一部署、部署后验证 |
| 小红书政策/登录限制 | 无法查询或发布 | 高 | 核心流程不依赖小红书；默认人工审核发布，不规避限制 |
| 双榜分类噪声 | AI 专题误收/漏收 | 中 | 可解释规则、排除名单、固定样本和人工抽检 |
| 公开报告中的版权/品牌风险 | 下架或声誉影响 | 低/中 | 原创设计、引用 GitHub 公共事实、明确来源和非官方声明 |

### Immediate Next Steps

1. 持续验证 daily/weekly Actions、Pages 部署及公开页面的综合主榜/AI 专题榜数据。
2. 连续积累 7 日快照；达到基线后核验两榜周增量与独立排名解释。
3. 单独实现并评估本地 Codex 可选摘要适配器；只通过受支持的 `codex exec`，不读取认证文件，也不让此项阻塞核心榜单。
4. 下一阶段评估原创图片、文件化人工审核状态和通知渠道；自动发布不在当前阶段。
