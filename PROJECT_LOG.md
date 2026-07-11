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
