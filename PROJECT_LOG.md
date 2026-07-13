# Project Log

## 2026-07-11 — MVP 初始化

- 解析用户提供的小红书笔记与主页公开内容，确认日榜 Top 3、周榜 Top 7/10、周期 Star、单项目卡片等信息结构。
- 建立 Python 3.12 项目、YAML 配置、CLI、测试和 GitHub Actions。
- 实现 GitHub Trending 与 REST Search 候选采集、REST 元数据补全和仓库去重。
- 实现日期快照、1 日/7 日基线、六因子排名与三种数据质量口径。
- 实现 Markdown、JSON、小红书文案三类产物及事实约束摘要。
- 生成真实的 `2026-07-11` 日榜样例。
- 验证：20 个 pytest 测试通过；Ruff 检查与格式检查通过；真实日榜端到端运行成功。

### 后续

- 积累至少 7 天快照，使日榜与周榜逐步切换到本地快照净增量。
- 增加原创 3:4 海报渲染器和人工审核流程。
- 可选接入结构化 LLM 中文摘要、GitHub Pages 和消息推送。

## 2026-07-11 — 公开仓库、项目主页与长期治理

### 目标

将本地 MVP 升级为可持续维护的公开项目：每次变更有日志、有测试、有语义化提交、有远端推送，并向读者提供独立的 GitHub Pages 数据主页。

### 变更

- 创建公开仓库 `https://github.com/wzgig/github-hotspots`，本地绑定为 `origin`。
- 新增项目级 `AGENTS.md`，固化“更新日志 → 测试 → 敏感信息检查 → Conventional Commit → push main → 验证 Actions/Pages”的交付闭环。
- 明确日志策略：人工代码/配置/文档变更必须更新 `PROJECT_LOG.md`；纯定时报告提交使用报告元数据与 bot commit 记录，避免每日日志膨胀和并发冲突。
- 新增自动构建的静态项目主页，读取最新日报和周报 JSON，展示日报 Top 3、周榜 Top 7、六因子排名口径及自动化流程。
- 新增 GitHub Pages 工作流；日报和周报的自动提交不再使用 `[skip ci]`，确保报告更新能够触发页面重建。
- 新增完整项目规划与运维规范，覆盖量化 KPI、阶段路线、依赖、风险、故障响应和回滚。
- 新增中国地区 Codex Chrome Extension 安装/修复说明。诊断确认 Chrome 正在运行，但扩展未安装且 native messaging 注册项缺失；根据安全规则，不以第三方 CRX 或脚本手工修复 native host。
- 新增本地 Codex 接入规范：本机已配置自定义 Responses-compatible provider，但公开仓库不记录实际 endpoint、model 或凭据；本地优先通过 `codex exec --ephemeral --sandbox read-only` 复用用户配置，CI 默认使用确定性摘要。
- 更新 README，加入公开仓库、Pages、Actions 状态和长期文档入口。

### 安全与发布决定

- 未读取、输出或提交 Codex API key、GitHub token、浏览器数据或本地认证文件。
- 小红书自动发布仍为 `TBD`；当前默认策略是生成素材后人工审核。
- 热点范围仍为 `TBD`；当前规划建议采用综合主榜并增加 AI/Agent 专题标签。

### 验证

- `pytest`：22 项全部通过，覆盖站点构建、排名、快照、报告与数据源解析。
- Ruff lint 与 format check：通过。
- `node --check site/app.js`：通过。
- Pages 本地构建：日报 3 项、周榜 7 项；本地 HTTP 返回 200。
- Playwright 视觉 QA：桌面 1440px 与移动 390px 均完整渲染；补充 favicon 后控制台为 0 error / 0 warning。
- 暂存区敏感信息扫描：未发现本地 Codex endpoint/model、GitHub Token、小红书访问 Token 或常见密钥格式。
- 首个公开提交：`62c3c69`（`feat: launch automated GitHub hotspots platform`），已推送至 `origin/main`。
- GitHub Pages：运行 `29148156765` 首次因 Pages 尚未启用而失败；启用 `build_type=workflow` 后重跑成功。
- 线上验证：`https://wzgig.github.io/github-hotspots/` 返回 HTTP 200，页面标题为“GitHub Hotspots / 开源热点编辑部”，首页特征内容存在。

## 2026-07-11 — 综合主榜、AI 专题榜与 MIT 许可证

### 目标

将已确认的产品决策落实为完整交付：同时生成“综合主榜 + AI 专题榜”，继续保持小红书人工审核发布，并为公开仓库选择清晰、宽松的开源许可证。

### 变更

- 在 `config/hotspots.yaml`、`src/github_hotspots/config.py` 和新增的 `src/github_hotspots/boards.py` 中定义两榜开关、标签、日/周 Top N、AI Topics 与 token/phrase-aware 关键词；AI 匹配使用精确 Topic 与完整 token/短语，避免把 `rails`、`maintainer` 等普通词误判为 AI。
- 在 `src/github_hotspots/pipeline.py` 中对全部合格候选和 AI 子集分别归一化、评分与排名；同一仓库允许进入两榜，但保留各自的独立 `rank`。
- 在 `src/github_hotspots/report.py`、`src/github_hotspots/cli.py` 和 `templates/dual_digest.md.j2` 中实现双榜 Markdown、Schema v2 JSON、综合榜 `*.xiaohongshu.md` 与 AI 榜 `*.ai.xiaohongshu.md`；顶层 `repositories` 继续指向综合主榜以兼容旧消费者。
- 在 `scripts/build_site.py` 与 `site/` 中增加独立的 AI 数据雷达，兼容旧报告 JSON，并保留桌面/移动端、键盘焦点和 reduced-motion 支持；修复桌面 1440px 下贴纸元素造成的 2px 横向溢出。
- 使用当天 GitHub 公开数据重新生成 `2026-07-11` 日榜和 `2026-W28` 周榜：日榜为综合 3 项 + AI 3 项，周榜为综合 7 项 + AI 7 项，并重建 `site/data/`。
- 新增标准 MIT `LICENSE`（`Copyright (c) 2026 Zicheng Wang`），并在 README、产品规范、项目规划、运维文档和 `AGENTS.md` 中说明允许个人/商业使用、修改和分发，但复制或分发时必须保留版权与许可声明。
- 更新 `prompts/project_master_prompt_zh.md`，把双榜契约、AI 正反例、两份人工审核稿、MIT 和 GitHub 完整交付闭环固化为后续维护提示词。
- 更新 Chrome Extension 指南；2026-07-11 已完成只读连接核验，未读取或记录 Cookie、浏览器存储、登录凭据、标签页标题或 URL。

### 验证

- Chrome Extension：连接成功，能够在不读取浏览器隐私数据的前提下访问用户授权的现有 Chrome 会话。
- `pytest`：30 项全部通过，总覆盖率 80%。
- `ruff check .` 与 `ruff format --check .`：通过。
- `node --check site/app.js`：通过。
- 真实端到端运行：日榜综合 Top 3 / AI Top 3、周榜综合 Top 7 / AI Top 7；四份小红书人工审核稿均已生成。
- Pages 本地构建：`daily=3 comprehensive / 3 AI`，`weekly=7 comprehensive / 7 AI`。
- Chrome 视觉 QA：桌面与 390px 手机均正确显示双榜；手机 AI 面板宽 358px、单列显示；桌面和手机均无横向溢出。
- 工作树与敏感信息预检：未发现 `.env`、Codex 凭据、GitHub Token、小红书 Token、Cookie 或常见密钥格式进入改动。

### 已知限制

- 当前 AI 专题归类依赖公开 Topics、名称和描述中的可配置规则，仍需通过人工审核处理边界项目，并根据实际内容质量迭代词表。
- 历史快照尚未积累满 7 天；当前样例的上榜项目主要使用明确标注的 GitHub Trending 周期 Star，不能表述为精确快照净增量。
- 当前只生成小红书文案草稿，不自动登录或发布；未来自动发布必须重新获得明确授权并满足平台规则、审核门禁和可撤回要求。
- 本地 Codex 摘要适配器尚未实现；未来只允许通过受支持的 `codex exec` 复用本地配置，不读取或复制认证文件。

## 2026-07-11 — 修复定时报表后的 Pages 刷新

### 原因

在线手动运行日报和周报后，bot 已分别提交 `e0fa2a4` 与 `f179f71`，但没有产生对应的 Pages 构建。原因是 GitHub 使用仓库 `GITHUB_TOKEN` 推送的提交不会再次触发其他 `push` 工作流；仅移除 `[skip ci]` 不能保证页面随定时报表刷新。

### 变更

- 更新 `.github/workflows/pages.yml`：保留人工 `push main` 与手动触发，同时监听 `Daily GitHub Hotspots`、`Weekly GitHub Hotspots` 的成功 `workflow_run` 完成事件。
- 对失败或取消的日报/周报不部署 Pages；只有源工作流成功时才执行静态数据构建与部署。
- 重新构建 `site/data/`，使仓库内站点数据与最新的 bot 日报/周报提交保持一致。
- 将项目规划中的 M2“Actions 首次线上验证”更新为已完成。

### 验证

- 日报工作流 `29157823597`：测试、真实报告生成、bot 提交全部成功。
- 周报工作流 `29157848568`：测试、真实报告生成、bot 提交全部成功。
- 修复前的 Pages `push` 运行 `29157812532` 对功能提交 `d01212b` 部署成功；bot 报告提交未触发新 Pages 运行，复现了刷新缺口。
- 本地 Pages 构建继续输出日榜综合 3 / AI 3、周榜综合 7 / AI 7。
- 修复提交 `dd25adc` 的 Pages `push` 运行 `29158010224` 成功。
- 再次手动运行日报 `29158031118` 后，bot 提交 `4285af2` 自动触发 `workflow_run` 类型的 Pages 运行 `29158046648`，部署成功，证明定时报表到页面刷新的链路已闭合。
- 线上页面与 `data/site-data.json` 均返回 HTTP 200；公开数据为日榜综合 3 / AI 3、周榜综合 7 / AI 7，Chrome 实际渲染数量一致且无横向溢出。

### 已知限制

- GitHub Actions 提示 `actions/checkout@v4` 与 `actions/setup-python@v5` 的 Node.js 20 运行时已弃用并被强制切换到 Node.js 24；当前不阻断任务，后续应在官方新主版本稳定后升级。

## 2026-07-11 — 中文候选库、原创海报与本地 Codex 受控选稿

### 目的

解决榜单文案反复使用“近期升温、聚焦”等固定句式和长英文简介混排的问题，为综合主榜与 AI 专题榜补齐可直接人工审核的小红书配图，并在不读取本地配置或凭据的前提下接入可选的 Codex CLI Schema 3.0 受控选稿能力。

### 变更

- 将 `summarizer.py` 扩展为 7 种事实型叙事角度，分别从公开定位、增长信号、主要语言、规模、Topics、最近推送和候选来源切入；中文强定位只根据精确 Topics 生成，证据不足时使用中性回退，不从自由描述的关键词推断能力，并增加否定语义、榜内多样性和禁用套话测试。
- 将 `prompts/repository_summary_zh.md` 重构为 Schema 3.0 受控选稿提示词，并新增 `schemas/repository_summary.schema.json`：每仓由程序生成 7 个完整候选，Codex 只能为整榜分配角度并逐字符复制所选候选，不能自由改写、翻译或补事实。
- 新增 `editorial.py` 本地 Codex 适配器：使用临时目录、stdin、`--ephemeral`、只读沙箱和 `--ignore-rules`；调用前通过 CLI 枚举已配置 MCP，为每个 server 追加 `enabled=false` 并二次验证全部关闭，同时禁用 shell、浏览器、插件、工具搜索和多代理。任何隔离、CLI、输出、候选或事实门禁失败都会整榜回退。
- 新增 `poster.py` 与 Pillow：每榜生成 1 张封面、每项目生成 1 张 `1200×1600` PNG；封面显示榜单 Top N、实际统计窗口和“已核验净增 Star / 净增基线积累中”等可信口径。找不到 CJK 字体或中文 glyph 时立即失败，不再静默生成方框字。
- 报告 JSON 升级到 Schema 3，加入 `editorial`、`assets`、逐项目 `assets.poster`、`window_start/end` 和 `manifest.json`；Manifest 升级到 Schema 2，记录 renderer/style 版本、源报告、窗口和 Top N。双榜图片与 manifest 先在同级临时目录完整生成，再整体替换旧目录。
- 新增 `rerender` CLI，可从冻结 JSON 重建文案和海报而不访问 GitHub；严格验证 Schema 1/2/3、双榜结构、必填事实、GitHub URL、排名、`delta_source`、有限 score/percentiles，并拒绝静默补零、跳过非法条目或输出 NaN/Infinity。
- 强化 `config.py`：`editorial`、`posters` 和 `codex_cli` 必须是 Mapping，布尔值严格解析，海报最大尺寸限制为 `2400×3200`。
- 日榜/周榜工作流安装 Noto CJK 字体，并在生成前运行 pytest、Ruff check 和 Ruff format check；提交步骤写入 `$GITHUB_STEP_SUMMARY`。默认后端仍为 `deterministic`，不会把本地 Codex 登录态带入 Actions。
- Pages 构建安装项目依赖，严格校验报告 Schema、必填结构、海报必须位于对应 `reports/<period>/assets/`、真实 PNG 格式、`1200×1600` 尺寸和 5 MB 上限；网站显示日报缩略图，并为全部项目提供同源 PNG 下载入口。
- 更新 README、项目总控提示词、产品规格、完整规划、运维规范、本地 Codex 安全方案和小红书参考拆解；明确每日 08:17、周一 08:27、`workflow_dispatch` 按需刷新、非事件实时边界、人工审核发布、MIT 许可证与长期图片归档风险。
- 使用冻结事实和当前 Schema 3.0 重建 `2026-07-11` 日榜与 `2026-W28` 周榜：分别生成 8 张和 16 张 PNG；综合主榜和 AI 专题榜共四次真实本地 Codex 受控选稿全部成功，均 `fallback_used=false`。

### 数据与接口影响

- 排名、候选发现和 GitHub 数字口径未改变；LLM 不参与搜索、AI 分类、候选写作、评分、日期、Star/Fork、URL 或海报决策，只在已冻结候选之间选择。
- 报告 JSON 从 Schema 2 增量升级到 Schema 3；顶层 `repositories` 和既有双榜路径继续保留。站点构建器可读取 Schema 1/2/3，但会拒绝未知或残缺报告。
- 新增公开配置 `editorial` 与 `posters`。当前项目级 `reasoning_effort_override: xhigh` 仅用于兼容已安装 Codex CLI，不修改用户全局配置，也不记录 provider、endpoint、model 或凭据。
- 小红书自动发布仍未启用；文案、封面和项目图全部标记为人工审核稿。

### 验证

- `pytest`：97 项全部通过，总覆盖率 80%。
- `ruff check .` 与 `ruff format --check .`：通过。
- `node --check site/app.js`、daily/weekly/pages 工作流 YAML 解析和 `git diff --check`：通过。
- Pages 本地构建：日榜综合 3 / AI 3，周榜综合 7 / AI 7；20 张项目图与 4 张封面通过 PNG、尺寸和路径校验后复制到站点构建目录。
- 本地 Codex：先验证当前 2 个已配置 MCP 的启用数量全部降为 0，再用 3 个公开冻结项目完成独立 Schema 3.0 冒烟，随后重建日榜/周榜四个榜单；全部使用 `codex-cli`、无回退，并通过 Schema、身份、URL、数字、质量警告、候选逐字符匹配、角度覆盖和禁用套话回查。
- 图片视觉与结构检查：封面包含窗口、Top N 和可信增长口径；24 张图片均为 `1200×1600`，Manifest Schema 2 与报告映射一致。
- Chrome 本地页面检查：数据状态正常，3 个日报海报缩略图、17 个其余项目下载入口全部存在；桌面已加载图片均为 `1200×1600` 且无破图，390px 手机视口无横向溢出，首屏导航与状态卡正常显示。

### Actions / Pages

- 本地实现与产物已完成；最新 SHA、图片提交范围、工作流摘要和线上下载链接已在后续“修复 Actions 质量门禁的 CI 环境污染”记录中完成闭环。

### 已知限制

- 真实 7 日快照仍需继续积累，当前部分榜单继续使用明确标注的 GitHub Trending 周期 Star。
- 本地 Codex 是可选受控选稿层，严格候选与事实门禁可能让整榜回退；自然度仍主要取决于确定性中文候选库，尚未建立不少于 30 个仓库的固定质量评估集和长期延迟/回退率基线。
- 当前不默认启用小时级或实时提交；同日多快照、API 预算、历史保留与并发写入需要独立设计。
- 当前日报图片约 1 MB、周报图片约 2 MB；按现有节奏估算 Git 历史每年约增长 495 MB，后续需要保留、压缩或外部归档策略。
- 不同系统可能选择不同 CJK 字体；相同输入只保证在同字体环境内稳定，跨系统 PNG 字节级一致性不作承诺。
- 小红书仍由用户人工选题、审稿、选图和发布；项目不会登录或自动操作账号。

## 2026-07-11 — 修复 Actions 质量门禁的 CI 环境污染

### 目的

修复日报工作流 `29163603991` 在 `Run quality gates` 阶段暴露的跨环境测试问题：GitHub Actions 自动设置的 `CI` / `GITHUB_ACTIONS` 被 Codex 适配器单元测试继承，导致 10 个本应验证受控调用与回退类别的测试提前进入 `disabled_in_ci` 分支。

### 变更

- 更新 `tests/test_editorial.py` 的自动夹具，在普通单元测试开始前清除外部 `CI` 与 `GITHUB_ACTIONS`，使测试结果不依赖启动 pytest 的宿主环境。
- 将“CI 默认禁用本地 Codex”测试参数化，分别覆盖 `CI` 和 `GITHUB_ACTIONS`；测试内部显式恢复目标变量，继续证明云端默认只使用确定性后端。
- 生产代码和工作流权限未改变；本次修复只消除测试环境污染，不允许 GitHub Actions 读取或调用用户电脑上的 Codex 配置。

### 验证

- 修复前本地复现：设置 `CI=true` 后，`tests/test_editorial.py` 为 10 failed / 3 passed，与 Actions 日志一致。
- 修复后定向验证：相同 `CI=true` 条件下 14 项 editorial 测试全部通过。
- 修复后完整门禁：相同 `CI=true` 条件下 98 项测试全部通过，总覆盖率 80%；Ruff lint、Ruff format check、`node --check site/app.js` 与 `git diff --check` 全部通过。
- 失败工作流在生成报告之前终止，没有创建报告文件、海报、site-data 或 bot 提交。

### 线上闭环

- CI 测试修复提交 `b418df2` 已推送；其 push Pages 运行 `29163740462` 成功。
- 日报工作流 `29163744881` 完整通过字体安装、98 项测试、Ruff、报告与 8 张海报生成及提交，生成 bot 提交 `cefa80b`；对应 `workflow_run` Pages `29163770005` 成功。
- 周报工作流 `29163782401` 在日报提交之后完整通过相同门禁、报告与 16 张海报生成及提交，生成 bot 提交 `b185c67`；对应 `workflow_run` Pages `29163813347` 成功。
- 线上页面已更新到 `2026-07-12` 日榜和 `2026-W28` 周榜，显示日榜综合 3 / AI 3、周榜综合 7 / AI 7；`site-data.json` 中 24 个 PNG 路径全部返回 HTTP 200 与 `image/png`，页面 20 个项目下载入口唯一且已加载缩略图无破图。
- Actions 仍提示 `actions/checkout@v4` 与 `actions/setup-python@v5` 的 Node.js 20 运行时弃用警告；GitHub 当前强制使用 Node.js 24 且任务成功，该警告不阻断本次交付。

## 2026-07-12 — 小红书用途解释、知识卡海报与 Pages 内容 V2

### 目的

解决现有内容虽然展示了 Star、语言、Topics 和增长数据，却没有回答“这个项目到底能做什么”的核心问题；同时把小红书文案、原创海报和 Pages 从工程数据看板升级为用途优先、证据受控的项目解释产品。

### 调研与决策

- 新增 `docs/XIAOHONGSHU_CONTENT_V2_PLAN.md`，记录小红书官方规范、搜索/推荐的可验证边界、四类目标受众、3/10/30 秒阅读任务、标题/正文/轮播/互动规范和三期人工 A/B 复盘方案。
- 明确不采用“固定冷启动池、CES 权重、黄金两小时”等缺少可靠公开证据的流量传言；内容优化只围绕可理解性、搜索词、收藏价值、真实互动和合规边界。
- 将本轮定义为兼容 Schema 3.0 的 V2 第一阶段；README 证据片段、逐主张引用、使用条件、限制和 `content_status` 进入后续 Schema 4.0 路线。

### 代码、提示词与出版变更

- 重构 `src/github_hotspots/summarizer.py`：七个 angle 不再轮换元数据开场，而是选择同一受控用途的七种自然表达；`one_line` 讲用途，三条 `highlights` 讲具体能力，`audience` 讲任务场景。加入严格 Topics/短语规则与局部否定保护，覆盖 C++ 测试、网页抓取、Office 自动化、代码审查插件、AI 渗透测试、本地会议转写、系统提示词库、Agent 编排/IDE/网关/skills、MCP、Bun 和 PostgreSQL Rust 实现等类别；证据不足时明确要求人工核对。
- 将 `prompts/repository_summary_zh.md` 升级为 Prompt 4.0 编辑标准的 Schema 3.0 兼容桥接版；本地 Codex 仍只能逐字符选择程序候选，但选稿优先回答“谁、动作、结果”，禁止元数据冒充功能、假实测、夸张词、法律/性能推断和覆盖人工审核兜底。同步更新 `prompts/project_master_prompt_zh.md`。
- 重构 `src/github_hotspots/report.py` 与 `templates/xiaohongshu.md.j2`：标题改为“几个项目到底能做什么”；正文增加先看结论、三条能力、适合谁、来源准确的上榜信号和可回答互动问题；小红书发布区只保留 `owner/repo` 搜索词，不放裸 URL，并标明 AI 辅助整理、人工审核和 Star 不代表功能质量。
- 将 `src/github_hotspots/poster.py` renderer 升级为 `2.0`、style 升级为 `open-source-knowledge-card-v2`：采用固定暖白知识卡、深色榜单页眉、确定性原创项目身份块、固定四格统计、“它能做什么 / 核心亮点 / 适合谁 / 为什么本期上榜”分区；长项目名和长摘要动态缩小/换行，增长文案严格区分快照、Trending、估算和异常值，图片只显示 `owner/repo` 搜索词。
- 更新 `site/index.html`、`site/app.js` 和 `site/styles.css`：首页承诺从“重新校准热度”转为“每天看懂 GitHub 热门项目”；日榜、周榜和 AI 榜直接显示功能清单；修复 390px 手机视口中 hero grid 的固有尺寸导致的横向溢出。
- 使用冻结的 2026-07-12 日榜和 2026-W28 周榜事实重新生成四份小红书审核稿、4 张封面、20 张项目卡、两个 manifest 及 `site/data/`；排名、仓库身份和 GitHub 数字未重新采集或改写。

### 数据与接口影响

- 报告 Schema 继续为 3，Manifest Schema 继续为 2；现有 rerender、Pages 构建和历史消费者保持兼容。
- `summary.one_line/highlights/audience` 的语义从“定位/元数据说明”收紧为“用途/具体能力/任务受众”，Pages 与海报会直接消费新的语义。
- 排名、Star/Fork、URL、日期、AI 分类和快照口径未改变；本轮不调用本地 Codex 自由生成事实，真实产物使用确定性后端重建。

### 本地验证

- `pytest`：117 项全部通过，总覆盖率 79%。
- `ruff check .`、`ruff format --check .`、`node --check site/app.js` 与 `git diff --check`：通过。
- 冻结事实重渲染：日榜 8 张 PNG、周榜 16 张 PNG，四份文案与两个 Manifest 成功生成；Pages 构建输出日榜综合 3 / AI 3、周榜综合 7 / AI 7。
- 图片目视 QA：抽查综合/AI 日周封面、Catch2、Firecrawl、Meetily 和 codex-plugin-cc；用途、三条能力、受众和增长口径均可读，长摘要无省略号截断，图片不含第三方 Logo 或裸域名。
- Chrome 本地 QA：桌面 2560px 下 `scrollWidth=2545`、无横向溢出；390px 手机下文档 `scrollWidth=375`、卡片宽 358px、功能正文 14.4px、20 个功能区全部存在、0 张破图；页面数据状态为 `DATA FEED READY`。

### 已知限制

- 当前 V2 仍依赖结构化仓库事实、精确 Topics 和少量否定保护的严格短语规则，不能替代完整 README 证据抽取；未知项目会进入人工核对，不生成听起来合理但无证据的能力。
- W28 周榜仍使用明确标注的 GitHub Trending 周期 Star，不是精确 7 日快照净增；封面不会汇总成精确新增。
- 海报暂不自动使用项目 Logo、README 图片或头像；许可证、安装条件和已知限制将在 Schema 4.0 证据模型中进入正式卡片字段。
- 小红书继续只生成审核稿和配图，不自动登录、发布或操作互动；最终 AI 辅助标识和平台规则由人工发布前确认。
- Actions 与 Pages 线上状态将在本提交推送后验证并追加闭环记录。

### 线上闭环

- 功能提交 `973b77e` 已推送到 `origin/main`。
- GitHub Pages `push` 运行 `29177133065` 成功完成构建与部署：<https://github.com/wzgig/github-hotspots/actions/runs/29177133065>。
- `https://wzgig.github.io/github-hotspots/` 与 `data/site-data.json` 均返回 HTTP 200；线上首页已包含“每天，看懂 GitHub 热门项目”和 `GITHUB PROJECTS, EXPLAINED`。
- 线上日报日期为 `2026-07-12`，首项 `catchorg/Catch2` 的用途摘要和三条能力已更新；对应 V2 PNG 返回 HTTP 200、`image/png`，字节数为 163,897。

## 2026-07-12 — README 证据化文案、Owner 头像与参考图海报 V3

### 目的

解决 V2 仍然依赖三条受控短句、项目解释不够完整、海报缺少 GitHub Owner 头像，以及公开文案重复展示“数据来自 GitHub 公开信息与本地快照”的问题。新版以用户提供的同类帖子为信息架构参考，先核验参考仓库真实 README 与许可证，再把可复用模板、证据采集、本地 Codex 写作、人工审核稿和 Pages 串成同一条安全流程。

### 参考核验与内容原则

- 核验参考仓库 `Imbad0202/academic-research-skills` 的 README、目录与 LICENSE；确认优质之处来自“项目定位 → 五条能力 → 核心解释 → 适合人群”的阅读顺序，而不是“神器、全自动、高效”等夸张词。
- 纠正参考图中的事实偏差：该仓库实际为 `CC BY-NC 4.0`，不是 MIT；README 明确强调人机协作与人工确认点，不能写成全自动论文生成器。
- 公开小红书正文与海报不再重复“数据来自 GitHub 公开信息与本地快照”，但排名数字、窗口、证据与数据质量仍保留在报告 JSON、Markdown 和 Pages 方法区中供核验。

### 代码、Prompt 与 Schema

- 新增 `evidence.py`、`publication_evidence.py` 与 GitHubClient 证据接口：按 Top 仓库读取 metadata 和清洗后的 README，限制 README 大小，剥离危险 HTML、徽章和过长代码块，并把外部文本始终标记为不可信数据。
- 新增安全头像缓存：仅接受 `avatars.githubusercontent.com` 的 HTTPS 图片，限制重定向、下载体积、像素和边长；Pillow 解码后重新编码为无元数据 PNG，按报告周期本地缓存，失败时使用确定性身份块。
- 将 Prompt/Schema 升级到 4.0。README 充分时，本地 Codex 可在证据语义内生成白话 `one_line`、最多 5 条 `capabilities`、`core_title/core_summary`、具体受众、前置条件、限制、许可证与逐字段 `evidence_ids`；README 缺失时只能复制单一受控候选。
- 冻结并回查仓库身份、URL、语言、Star/Fork、排名、增量、README SHA 和许可证原文；证据 ID 不存在、数字无证据、许可证猜测、禁用套话、输出结构或隔离失败时整榜回退。
- 修复本机结构化输出接口不支持 JSON Schema `uniqueItems` 的兼容问题：从外部 Schema 删除该关键字，继续由程序侧严格检查能力、亮点、证据 ID 和榜内内容是否重复。
- 将面向海报的文字上限收紧为完整短句边界，避免长段落被截断；海报渲染遇到放不下的文字仍直接失败，不发布残缺图片。
- `rerender` 新增 `--refresh-evidence`；离线重绘会保留已有丰富摘要、Owner 头像、README SHA/来源和原始 Codex editorial 元数据，不需要重新调用模型或重新收集排名事实。

### 海报、文案与 Pages

- `poster.py` 升级为参考图信息架构 V3：深绿日期/期号页眉、金色排名圆、Owner 头像身份卡、完整项目定位、许可证、四格统计、五条能力、核心亮点长说明、适合人群和简洁底栏。
- 小红书模板展示最多 5 条能力、核心亮点、前置条件、限制和许可证；许可证文件导航语句不会再被误写成许可证限制，英文普通限制会在证据范围内改写成中文。
- Pages 日榜卡片改为展示 5 条能力和独立核心亮点区块，并加入许可证标签；站点 footer 改为产品范围和人工发布策略，不再重复数据来源口号。
- 使用冻结的 `2026-07-12` 日榜与 `2026-W28` 周榜排名事实，通过本机 `codex exec` 重建综合/AI 四个榜单；四批均为 `used_backend=codex-cli`、`fallback_used=false`。生成 20 张项目卡和 4 张封面，共 24 张 `1200×1600` PNG，并缓存 13 个唯一 Owner 头像。
- 重新生成四份小红书人工审核稿、两份 Markdown/JSON、两个 Manifest 和 Pages `site-data`；日报/周榜原有仓库、rank、Star、Fork、周期增量与 `delta_source` 与提交前冻结报告逐字段一致。

### 文件与模块

- 核心：`src/github_hotspots/{evidence,publication_evidence,github_client,editorial,summarizer,pipeline,report,rerender,poster,cli}.py`
- 协议：`prompts/repository_summary_zh.md`、`schemas/repository_summary.schema.json`、`templates/xiaohongshu.md.j2`、`config/hotspots.yaml`
- 页面：`scripts/build_site.py`、`site/{index.html,app.js,styles.css,data/*}`
- 文档：`README.md`、`docs/{LOCAL_CODEX_API,PRODUCT_SPEC,PROJECT_PLAN,XIAOHONGSHU_CONTENT_V2_PLAN}.md`、`prompts/project_master_prompt_zh.md`
- 产物：`reports/daily/2026-07-12*`、`reports/weekly/2026-W28*`、两期 `assets/` 与 `avatars/`
- 测试：新增证据、GitHubClient 与证据编排测试，并扩展 editorial、summarizer、poster、report、rerender、CLI 和站点构建测试。

### 验证

- `pytest`：182 项全部通过，总覆盖率 80%。
- `ruff check .`、`ruff format --check .`、`node --check site/app.js` 与 `git diff --check`：通过。
- 冻结事实对比：当前日榜和周榜两榜的 `full_name/rank/stars/forks/star_delta/delta_source` 与变更前报告完全一致。
- 出版包检查：日榜 8 张、周榜 16 张图片全部为 `1200×1600` PNG；20 个榜单项目均有 5 条互不重复能力、`readme_enriched`、匹配的 README SHA 和可读取的本地头像 PNG。
- Pages 构建：`daily=3 comprehensive / 3 AI`，`weekly=7 comprehensive / 7 AI`。
- Playwright 本地 QA：桌面 `1440×1000` 与移动 `390×844` 均正确渲染；日报 5 条能力和核心亮点可见，海报缩略图全部加载，控制台无错误，移动端无横向溢出。
- 敏感信息扫描：47 个变更文本文件未发现 `.env`、API key、GitHub Token、小红书 `xsec_token`、Bearer 凭据、本机 Codex provider/model 或用户级配置路径。

### 已知限制

- GitHub Actions 默认仍使用 `deterministic`，不会获得用户电脑的本地 Codex 登录态；如未来需要云端 README 证据化自由写作，必须另行明确授权并使用 GitHub Secrets，不能复制本机凭据。
- W28 周榜增长仍来自明确标注的 GitHub Trending 周期 Star，不是本地 7 日快照净增。
- 许可证限制只在 README 中存在可逐字核验的原文时展示；涉及法律条件的英文原句可能保留，以免翻译改变含义。
- Owner 头像按报告周期缓存；远端不可用、格式不合法或超限时会使用身份占位图，不阻断榜单生成。
- 小红书继续由人工审核和发布；当前不自动登录、发布、评论或操作账号。

### 线上闭环

- 功能提交 `81abb42` 已推送到 `origin/main`；公开仓库为 <https://github.com/wzgig/github-hotspots>。
- GitHub Pages `push` 运行 `29179515822` 成功完成站点构建与部署：<https://github.com/wzgig/github-hotspots/actions/runs/29179515822>。
- 项目页 <https://wzgig.github.io/github-hotspots/> 与 `data/site-data.json` 均返回 HTTP 200；线上数据为 `2026-07-12` 日榜和 `2026-W28` 周榜，数量分别为日榜综合 3 / AI 3、周榜综合 7 / AI 7。
- 线上首项 `catchorg/Catch2` 已显示 `readme_enriched` 文案与核心亮点“贴近 C++ 表达式的测试写法”；V3 海报返回 HTTP 200、`image/png`，字节数为 200,780：<https://wzgig.github.io/github-hotspots/generated/reports/daily/assets/2026-07-12/2026-07-12.comprehensive.01.catchorg--catch2.png>。
- Actions 仍提示 `actions/checkout@v4`、`actions/setup-python@v5`、Pages 相关 actions 的 Node.js 20 运行时弃用，并由 GitHub 强制切换到 Node.js 24；本次构建与部署成功，该提示不影响当前交付，但后续应升级对应 action 主版本。

## 2026-07-12 — Signal Broadsheet 首发、发布工作台与本地 Codex 自动化

### 目的

将接近发布的参考风格版本升级为 GitHub Hotspots 自有产品：用原创视觉和证据化白话文案完成 `D001/W001` 首发，同时把日报每天、周报每周日的内容生产、质量门禁、GitHub 推送、Pages 刷新和本地小红书发布包串成可持续运行的流程。

### 变更

- 将编辑协议升级为 Prompt 4.1 / Schema 4.0，加入 3/10/30 秒阅读任务、逐字段证据、README SHA、许可证、冻结事实和整榜回退门禁；日报、周报使用不同开场、互动问题和可搜索的 `owner/repo` 标识，删除“近期升温”等重复套话。
- 将海报 renderer 升级为 `4.0`、style 升级为 `signal-broadsheet-v1`，形成“开源热点编辑部·信号报”原创品牌：综合榜使用米纸热力格，AI 榜使用黑底雷达，日报/周报分别显示 `24H/Dxxx` 与 `7D/Wxxx`，项目卡包含 Owner 头像、五项 Signal Rail、核心亮点和适用人群。
- 统一配置化公开期号：2026-07-12 为日报 `D001`、周报 `W001`；首发日前为 Preview。报告、Manifest、海报、Pages 和发布包共用同一期号，周报首发锚点必须是周日。
- 新增 `publish` 发布工作台：`publish/current/TODAY.md` 汇总当前日报/周报；每榜提供 `TITLE.txt`、`CAPTION.txt`、`REVIEW.md`、有序 PNG、周期级 `CHECKLIST.md` 与 `MANIFEST.json`。发布 Manifest 包含生成器版本、内容指纹、文案/审核稿/图片哈希和实际 materialization；历史包轮转到本地 `archive/`，不进入 Git 历史。
- 新增本地 Codex 主链路：Windows 日报 07:30、周日周报 08:45；任务只调用当前用户已安装的 `codex exec`，不读取 endpoint、provider、model、My Codex 密钥或认证文件。
- 强化无人值守安全边界：本地 `HEAD` 为代码信任锚；只接受远端日期化报告产物变化；所有 worktree 使用本地受信 verifier；严格校验当前 Prompt/Schema/期号/renderer/style、非空双榜和完整 PNG chunk/CRC；推送前完成 publish preflight、路径白名单和 Secret 扫描；禁止强推，远端代码变化时中止并等待人工更新。
- 修复 Windows PowerShell 5.1 原生命令日志兼容性：`git fetch`、`gh` 等工具即使成功也会把进度写到 stderr，runner 现在合并记录两条流并以真实退出码判定成功，避免把正常进度误报为计划任务失败。
- 新增 publish 同步指纹、跨卷复制语义、ISO week-year 归档、共享锁、陈旧 state worktree 清理、30 日运行日志和 `China Standard Time` 注册门禁；IDE 工作树不会被 reset、clean 或 rebase。
- GitHub Actions 调整为本地优先的 deterministic 兜底：日报 09:17、周日周报 10:27；发现同日期完整 Codex 产物时跳过。Actions 运行中远端前进时不再自动 rebase 旧报告；兜底成功后显式 dispatch Pages，普通用户 push 继续使用 Pages `push` 触发。
- 升级 Pages actions 主版本并重建 `site/data/`；网站顶部显示 `D001/W001`，项目能力区由三项更新为五项。
- 使用冻结的 2026-07-12 / 2026-W28 排名事实重新生成四份 Codex 文案、4 张封面和 20 张项目卡；仓库身份、排名、URL、Star、Fork、增量和 `delta_source` 与变更前逐字段一致。
- 补全海报中文禁则换行：闭标点不会落在新行开头，开引号/开括号不会停在行末；当大字号会形成“单个汉字 + 闭标点”的孤行开头时自动缩小一级字号，并以回归测试覆盖。

### 文件与模块

- 核心：`src/github_hotspots/{automation,publish_bundle,poster,report,editorial,config,cli}.py`
- 自动化：`scripts/automation/{run_scheduled,register_tasks}.ps1`、`.github/workflows/{daily,weekly,pages}.yml`
- Prompt/配置：`prompts/{repository_summary_zh,project_master_prompt_zh}.md`、`config/hotspots.yaml`
- 发布与文档：`publish/README.md`、`docs/{AUTOMATION,PUBLISHING_PLAYBOOK,LOCAL_CODEX_API,PRODUCT_SPEC,PROJECT_PLAN,XIAOHONGSHU_CONTENT_V2_PLAN,OPERATIONS}.md`、`README.md`
- 首发产物：`reports/daily/2026-07-12*`、`reports/weekly/2026-W28*`、两期 `assets/`、`site/data/*`
- 测试：新增 automation/publish bundle 测试并扩展 config、poster、report、CLI、editorial 和 site builder 测试。

### 验证

- `pytest`：230 项全部通过，总覆盖率 81%。
- `ruff check .`、`ruff format --check .`、`node --check site/app.js`、`git diff --check`：通过。
- 两个 PowerShell 自动化脚本完成语法解析；daily/weekly/pages 三个 workflow 完成 YAML 解析。
- 标准库严格门禁：日报 8 张、周报 16 张 `1200×1600` PNG；综合榜与 AI 榜均为 `used_backend=codex-cli`、`fallback_used=false`，Prompt 4.1 / Schema 4.0 / renderer 4.0 / Signal Broadsheet V4 全部匹配。
- 冻结事实复核：日报综合 3 / AI 3、周报综合 7 / AI 7 的 `full_name/rank/stars/forks/star_delta/delta_source/html_url` 与变更前完全一致。
- 发布工作台复核：`D001-C`、`D001-A`、`W001-C`、`W001-A` 的标题、正文、检查清单、内容指纹、图片顺序、尺寸和 SHA-256 全部通过；正文保留“AI 辅助整理｜人工发布”，不含内部报告路径或数据来源口号。
- 视觉抽检：日报综合/AI 封面、Catch2、周报 `system_prompts_leaks` 与 OfficeCLI 项目卡无溢出、无旧版深绿/圆章/四格仪表盘残留；中文逗号行首、开引号行末问题已消除，Owner 头像和正文均可读。
- `register_tasks.ps1 -WhatIf` 已验证；实际任务注册、提交推送、Actions 与 Pages 线上状态在本次交付的推送后继续核验。
- 实际计划任务已注册为 Ready；`run_scheduled.ps1 -Period daily/weekly -RunDate 2026-07-12 -SkipPagesWait` 两条冒烟链路均通过可信远端校验、隔离 worktree、严格 bundle 验证、发布包同步和安全清理，且没有再次调用 Codex。

### 安全与发布决策

- 未读取、复制、输出或提交本地 provider endpoint、My Codex 密钥、Codex auth/config、GitHub Token、Cookie 或浏览器资料；本地能力只通过已安装 Codex CLI 复用。
- 小红书仍固定为人工审核、人工发布；自动登录、发帖、评论和账号操作不在当前范围。
- `publish/current`、`publish/archive` 和本地运行日志继续由 `.gitignore` 排除；公开仓库只保存可复现的报告、海报、代码和文档。

### 已知限制

- 本地 Codex 任务要求 Windows 用户保持登录、系统时区为 `China Standard Time`、网络可用且项目 `.venv`/Codex CLI 有效；关机或注销时由稍后的 Actions deterministic 流程兜底。
- Actions 无法访问个人电脑的 Codex 会话，也不能把 `publish/current` 写回离线电脑；必要时需拉取报告后在本机重新运行 `publish`。
- 2026-W28 的部分周期 Star 仍来自明确标注的 GitHub Trending 信号，不是完整 7 日快照净增量。
- `publish/archive` 为防止延后帖子丢失而不自动删除，长期会增长；正式清理或导出策略仍需单独设计。
- 小红书表现数据仍需人工记录；自动读取平台数据、自动发布和小时级/近实时数据模型均属于后续独立范围。

### 线上状态

- 当前条目记录提交前的本地完成状态；提交 hash、Actions run、Pages 部署和 Windows 计划任务实装结果将在推送后核验，并在本次用户交付说明中给出。

## 2026-07-13 — 发布历史、防覆盖机制与自动化可靠性修复

### 目的

解决 `publish/current` 后一天覆盖前一天、旧期只能依赖本机忽略目录找回的问题，并主动审计日报/周报自动化中的潜在数据、并发、跨平台和发布故障。目标是让每期生成基线可以在 GitHub 永久查找，同时继续保留本机最新完整图片工作台和人工发布边界。

### 发布历史与本机工作台

- 新增 Git 跟踪的薄历史：`publish/history/<period>/<year>/<report-stem>/<fingerprint前12位>/`。每个修订保存 Manifest、Checklist、两榜 Title/Caption/Review，不重复复制 PNG；图片通过 `reports/.../assets/` 路径、SHA-256 和尺寸核验。
- 新增 `publish/history/INDEX.json` 与可点击的 `INDEX.md`；回填 `2026-07-11` 预览日报、`D001`、`D002` 和 `W001`，共 4 个日期/周期记录，history 内 PNG 数为 0。
- `publish/current` 继续作为每个周期最新、带完整图片的上传工作台；`publish/archive` 继续保护本机人工修改；`publish/history` 作为公开、可版本化的自动生成基线。三者职责不再混用。
- 相同内容指纹重复执行保持幂等，不再产生 `r02/r03/...` 重复 archive 或 history；同一期内容变化时才新增修订。
- 同指纹 history 修订被改坏时先在临时目录重建并完整验证，再用可回滚 rename 替换损坏目录；不会因“目录已经存在”永久卡住自动修复。
- 损坏 history 修复后的旧目录隔离到 Git 忽略的 `publish/archive/history-recovery/`；若 Windows 文件锁导致隔离副本暂时无法删除，已验证的新 revision 仍保持成功，不会污染历史索引或让后续无人值守任务持续失败。
- 默认拒绝旧日期替换较新的 `current`；只回填历史使用 `--history-only`，明确需要把旧期放回工作台时才使用 `--activate-older`。新增 `publish-history-index` 重建命令。
- current 快速复用不再只看 Manifest 指纹，而会核验 Checklist、Title、Caption、Review、全部 PNG 的哈希和尺寸；文件被改动或缺失时归档旧包并原子重建，激活失败会恢复原目录。
- 发布工作台图片改为强制独立副本，不再使用 NTFS 硬链接；人工裁剪或标注 `current` 图片不会污染 `reports` 源图、Pages 资产和 history 哈希。

### 自动化与数据 Bug 修复

- 修复 Windows PowerShell 5.1 将合法 Pages `[]` 查询结果误判并访问空对象 `status` 的问题；`gh` stdout/stderr 分离，临时查询失败在总超时内重试，失败/成功/缺字段状态均安全解析。
- 将本地 runner 与 daily/weekly Actions 的 `git fetch` 改为显式更新 `refs/remotes/origin/main`，立即冻结并验证完整远端 SHA，避免读取陈旧跟踪引用。
- 本地 runner 与 Actions 均暂存 history 索引和当期修订；报告完整但 history 缺失或损坏时只修复 history，不重新调用 Codex，也不以 deterministic 文案覆盖现有 Codex 报告。新增标准库 `verify-history` 门禁：重新计算完整内容指纹、全部文本/图片哈希与尺寸，并从所有 revision Manifest 重建期望 INDEX.json/INDEX.md 后逐结构比较；该门禁已纳入 skip、远端胜出和 push-race 判断。
- rebase 后的 publication preflight 若再次改动 history index，会中止并从新 worktree 重试，禁止带脏树报告 push 成功。
- 文本指纹统一按 LF 规范化，并新增 `.gitattributes`，消除 Windows CRLF 与 Actions/Linux LF 导致的伪修订、哈希失配和 current 误损坏。
- 快照存储加入 Windows/POSIX 跨进程锁、锁内重读合并、唯一临时文件、`fsync`、原子替换和失败清理，避免日报/周报并发覆盖同日仓库数据。
- GitHub `pushed_at` 先转换到配置时区再计算活跃日期，修复北京时间凌晨项目被低估一天的问题。
- 海报尺寸契约统一为 `600×800` 至 `2400×3200` 范围内的合法 3:4 尺寸；publish 与 Pages 不再硬编码 `1200×1600`，同时继续以该尺寸作为默认值。
- 测试临时目录固定到仓库忽略的 `.pytest_tmp/`，绕过本机全局 pytest 死 reparse point 导致的 WinError 5 清理失败。

### 文件与模块

- 发布核心：`src/github_hotspots/{publish_bundle,cli,automation}.py`、`publish/history/**`、`.gitattributes`、`.gitignore`。
- 自动化：`scripts/automation/run_scheduled.ps1`、`.github/workflows/{daily,weekly}.yml`。
- 数据正确性：`src/github_hotspots/{snapshot,ranking,pipeline,config}.py`、`scripts/build_site.py`、`site/data/{site-data.json,site-data.js}`。
- 测试：`tests/test_{automation,powershell_automation,publish_bundle,cli,config,ranking,snapshot,site_builder}.py`。
- 文档：`README.md`、`publish/README.md`、`docs/{AUTOMATION,LOCAL_CODEX_API,OPERATIONS,PRODUCT_SPEC,PROJECT_PLAN,PUBLISHING_PLAYBOOK}.md`。

### 验证

- `pytest`：260 项全部通过，总覆盖率 81%；仓库内 `.pytest_tmp` 使 AGENTS 规定的原始命令可直接成功退出；新增回归测试覆盖 Windows 锁定 history recovery 隔离目录的场景。
- PowerShell 5.1 行为测试：Pages 查询重试、损坏 current 修复、Checklist 哈希、旧期防降级、无效 Manifest recovery archive、激活失败回滚等 8 项通过；runner 语法解析通过。
- `ruff check .`、`ruff format --check .`、daily/weekly/pages YAML 解析、`node --check site/app.js`、`git diff --check`：通过。
- `verify-history`：`2026-07-11`、`2026-07-12`、`2026-07-13` 日报与 `2026-W28` 周报全部通过；历史索引 4 项，全部有可点击的综合榜/AI 榜文案入口，无 PNG 重复提交。
- Pages 数据已从仓库内旧的 D001 重建到最新 `D002 / 2026-07-13`，日榜综合 3 / AI 3、周榜综合 7 / AI 7。
- 本机 current 实测保持日报 `D002 / 2026-07-13`、周报 `W001 / 2026-W28`；相同输入连续发布不再新增 archive，尝试用 `D001` 覆盖 `D002` 会被拒绝。
- Windows 计划任务已重新注册为 `Ready`：日报下一次 `2026-07-14 07:30`，周报下一次 `2026-07-19 08:45`。

### 已知限制

- `publish/history` 保存自动生成基线，不会自动捕获之后在 `publish/current` 中进行的人工改稿或平台链接；最终发布版仍需另行运营记录。
- 薄历史不复制 PNG。同日期重渲染会更新 `reports/.../assets/<stem>`；旧图片字节仍可从对应 Git 提交恢复，但 history Manifest 当前没有单独记录图片所属提交。长期可改为内容寻址资产路径或记录 Git blob/commit。
- Pages 当前继续展示报告与海报，不直接渲染发布文案历史；公开历史入口是 GitHub 仓库中的 `publish/history/INDEX.md`。
- 小红书仍为人工审核、人工发布；本次没有增加自动登录、发帖、评论或账号操作。
