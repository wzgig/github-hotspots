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
