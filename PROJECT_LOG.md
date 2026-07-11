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
