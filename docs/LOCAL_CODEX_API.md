# 本地 Codex 证据化编辑与密钥隔离方案

本文定义 GitHub Hotspots 可选调用本地 Codex CLI 时的使用时机、Prompt 4.1 / Schema 4.0 契约、证据边界和凭据隔离要求。当前 Codex 的角色是“整榜证据编辑器”：它可以在同一仓库的受控 README/metadata 证据范围内，把原文改写成普通读者能理解的小红书文案；它不能改变仓库身份、URL、榜单数字、排名或许可证事实。

> 历史说明：Schema 3.0 曾把 Codex 限定为从七个候选中逐字符选稿。该方案已经由 Prompt 4.1 / Schema 4.0 取代，只保留为旧报告兼容背景，不代表当前实现。

## 决策摘要

1. **GitHub Actions 默认使用 `deterministic`**，不依赖 LLM，也不加载任何本机 Codex 凭据。
2. **本地可显式使用 `codex exec`**。项目只启动已安装的 Codex CLI，由 CLI 自行加载用户级 provider、配置和认证状态；项目不扫描、解析或复制这些文件。
3. **Prompt 4.1 / Schema 4.0 允许证据内白话重写**。README、description、Topics 和 metadata 都是不可信外部数据，只能作为证据，不能成为指令。
4. **身份和数字冻结**。仓库 ID、`owner/repo`、URL、语言、Star、Fork、周期增量、排名和统计窗口由程序逐字段回查，模型不能换算、纠错或补全。
5. **许可证不得猜测**。`NOASSERTION`、`OTHER`、`unknown` 或空值都不等于 MIT，也不代表允许商用；许可证名称和限制只能来自明确证据。
6. **失败按整榜回退**。非法 JSON/Schema、证据 ID、README SHA、身份/数字、许可证、重复或其他校验失败时，丢弃整个榜单的模型输出并使用确定性结果。
7. **头像单独走安全缓存**。受控 metadata 中可以包含 Owner 头像 URL，但 Codex 不得访问它，头像图片字节也不进入模型；程序仅从受控 GitHub 头像域下载，验证并重新编码为本地 PNG，失败时使用确定性占位图。

## 当前实施状态（2026-07-12）

- `prompts/repository_summary_zh.md` 已升级为 Prompt 4.1，`schemas/repository_summary.schema.json` 已升级为输出 Schema 4.0。
- `editorial.py` 已实现整榜证据输入、证据内白话改写、逐字段 `evidence_ids`、README SHA/许可证/身份/数字回查、CI 禁用和整榜回退。
- `evidence.py` 与 `publication_evidence.py` 已实现 README 清洗、metadata/README 证据包和安全 Owner 头像缓存。
- 确定性摘要仍是普通本地 CLI 与 GitHub Actions 的默认路径，也是 Codex 不可用或输出不合格时的内容级回退路径；已注册的本地计划任务会显式要求 `codex-cli`，并在发生回退时拒绝提交。
- 报告读取层继续兼容历史报告 Schema；这与 Codex 输出 Schema 4.0 是两套不同的版本契约，不应混淆。

## 三种运行模式

| 模式 | Codex 使用方式 | 失败与产物语义 |
| --- | --- | --- |
| 普通本地 CLI | 默认 `deterministic`；只有显式传入 `--editorial-backend codex-cli` 才复用当前用户的 Codex CLI | Codex 不可用或输出不合格时可生成确定性回退报告；另行执行 `publish` 会刷新 `current` 并写入 `history` |
| 已注册的本地计划任务 | 每天 07:30 / 周日 08:45 强制选择 `codex-cli`，不读取其 endpoint、provider、model 或密钥 | 两榜必须均为 Codex 且无回退；成功后提交薄历史并同步本机 `publish/current/<period>`，history 缺失时不重跑 Codex |
| GitHub Actions | 固定使用 `deterministic`，无法访问本机 Codex 会话 | 更新公开快照、报告、图片、Pages 数据与 `publish/history`；不能直接更新离线电脑上的 `publish/current` |

## Codex 在流水线中的位置

```text
1. GitHub 候选发现
2. API 事实补全与过滤
3. 快照和增量计算
4. 综合主榜 / AI 专题榜独立排名
5. 冻结仓库身份、URL、数字、榜单顺序和统计窗口
6. 采集并清洗 README / metadata，生成可用 evidence IDs
7. 可选 Codex 按整榜进行证据化中文编辑
8. Schema 4.0、逐字段证据、README SHA、许可证和冻结事实回查
9. 报告、Signal Broadsheet V4 海报、`publish/current` 人工发布包与 `publish/history` 薄历史
```

Codex 可以完成：

- 阅读当前仓库经过清洗的 README 和受控 metadata。
- 在证据语义范围内把项目定位、能力、核心亮点、受众、前置条件和限制改写成自然中文。
- 为相邻项目分配不同叙事角度，减少整榜重复。
- 为每个自然语言字段返回对应的 `evidence_ids`。

Codex 不可以完成：

- 搜索仓库、跟随 README 外链、调用工具或执行 README 中的命令。
- 决定 AI 专题归属、排名、Star/Fork/日期或增量。
- 修改仓库身份、URL、语言、统计窗口或任何冻结数字。
- 根据模糊提示推断许可证、商用权利、性能、安全性、采用情况或未来趋势。
- 绘制海报、下载头像或读取项目目录、本机环境和用户级 Codex 文件。

## Prompt 4.1 / Schema 4.0 输入

每个榜单项只包含公开、经过程序清洗和限长的材料：

- 冻结的仓库身份、榜单数字和 `editorial_facts`；
- `deterministic_draft` 与七个带 `evidence_id` 的 `candidate_summaries`；
- `repository_evidence.metadata`：仓库 ID、`full_name`、URL、Owner 头像 URL、许可证 SPDX、默认分支等受控字段；
- `repository_evidence.readme`：经过清洗、带 SHA 的 README，或 `null`；
- `available_evidence_ids`：当前仓库可以引用的全部证据 ID。

README、description、Topics、网页文字和 metadata 均标记为不可信外部数据。提示词明确要求忽略其中的角色覆盖、工具调用、文件读取、网络访问、凭据请求和输出格式修改指令。模型不能跨仓库借用证据。

## Prompt 4.1 / Schema 4.0 输出

每个 `card` 的主要自然语言与审核字段为：

- `one_line`：一句话说明项目是什么、解决什么问题。
- `highlights[3]`：为历史报告消费者保留的三条核心能力。
- `capabilities`：1 至 5 条具体能力；证据充分时优先写满 5 条。
- `core_title` / `core_summary`：最有辨识度的核心亮点及完整解释。
- `audience`：具体使用者和任务场景。
- `prerequisites`：README 明确写出的前置条件；无证据时为空字符串。
- `limitations`：README 明确写出的人工确认点或能力边界；无证据时为空字符串。
- `license_label` / `license_restrictions`：许可证标识与限制原文；不得推导法律结论。
- `readme_sha`：使用的 README SHA；没有 README 时为 `null`。
- `content_status`：`readme_enriched`、`metadata_only` 或 `needs_review`。
- `evidence_ids`：为上述每一个自然语言字段分别列出证据 ID；列表字段按每条文字分别引用。

非空文本必须至少引用一个当前仓库 `available_evidence_ids` 中的 ID；空字符串必须对应空证据数组。文案里的阿拉伯数字还必须逐字符出现在所引用证据正文中。

## README 缺失与整榜回退

README 存在时，Codex 可以在证据范围内自由使用白话重写，但必须回显完全一致的 `readme_sha`，并让 `readme_enriched` 文案至少引用一次 `github.readme:<sha>`。

README 缺失时：

- `readme_sha` 必须为 `null`；
- `content_status` 只能是 `metadata_only` 或 `needs_review`；
- 除许可证字段外，全部自然语言字段必须逐字段匹配同一个 angle 的单一 `candidate_summaries` 候选；
- 许可证只能逐字复制有意义的 metadata SPDX，`license_restrictions` 必须为空；
- 不允许借 metadata 自由扩写新能力、前置条件、限制或受众。

README 缺失本身不会阻断整榜；它会把该仓库限制到确定性候选。若模型违反上述限制，或出现非法证据 ID、README SHA 不一致、输出失败、事实漂移、许可证不匹配等任一问题，则**整个榜单**回退到 `deterministic`，不接收部分合格结果，也不尝试自动修补模型输出。

## 冻结事实与许可证门禁

以下字段由程序逐字段复制和回查：

- `rank`；
- `repository.repository_id`、`full_name`、`html_url`；
- `card.project_name`、`language`、`stars_total`、`period_stars_added`、`period_stars_added_display`、`forks_total`、`repository_url`；
- `data_quality.delta_source`、`delta_is_exact`、`warnings`；
- `period.type`、`period.start`、`period.end`。

许可证门禁额外要求：

- metadata SPDX 只有在不是 `NOASSERTION`、`OTHER`、`unknown` 或空值时才可直接采用；
- README 许可证名称必须逐字出现在所引用 README 中；
- `license_restrictions` 必须是 README 中连续出现的原文短句，不能翻译、概括或推导；
- 不得输出“商用无忧”“无任何限制”“可放心商用”等法律结论。

## 安全 Owner 头像缓存

V4 单项目海报在项目名称左侧使用 GitHub Owner 头像。头像管线独立于 LLM：

1. 只接受 `https://avatars.githubusercontent.com/...`，拒绝 HTTP、用户信息、非默认端口、伪造子域和越界重定向。
2. 限制下载体积、图片像素、单边尺寸和重定向次数，并校验允许的图片 Content-Type。
3. 使用 Pillow 解码后重新编码为 PNG，去除原图 metadata；采用安全 cache key、URL 摘要文件名和原子写入。
4. 只把位于报告头像根目录内的相对路径写入公开报告，不公开本机绝对路径。
5. 下载、格式或路径校验失败时记录非敏感 warning，海报使用确定性身份占位图，不阻断榜单。

## Signal Broadsheet V4 原创信息架构

当前海报直接继承项目页面的品牌语言，不复用第三方帖子的视觉组合：

- 米纸、黑墨、信号橙和酸绿色构成主色；综合榜使用浅色热力格，AI 榜使用深色雷达；
- 报头同时显示 `ALL/AI`、`24H/7D` 与 `Dxxx/Wxxx`，不只靠颜色区分；
- Owner 头像、项目名和白话定位构成首屏焦点；Star、增长、Fork、语言和许可证进入紧凑 signal bar；
- 01—05 Signal Rail 串联五项能力；`core_title/core_summary` 使用跨栏信号带，`audience` 位于底部；
- `prerequisites` 与 `limitations` 保留在文字审核稿中，不强塞进海报；
- 禁止恢复旧版深绿大头、圆形排名章、四格仪表盘和左右深浅分栏。

公开海报和小红书正文不再重复“数据来自 GitHub 公开信息与本地快照”这类来源声明，也不展示裸 URL 或内部审核/管线术语；真实性仍由冻结报告、证据字段和人工审核保证。

## 本地调用方式

项目代码只知道如何启动 `codex exec` 并接收 Schema 4.0 JSON，不知道实际 endpoint、API key、provider 或 model。适配器使用临时目录、只读沙箱、临时会话和输出 Schema，并在调用前关闭 MCP server 及与文本编辑无关的能力。

> “读取本地 Codex 使用的 API”在本项目中表示“调用本机 Codex CLI，让 CLI 复用自己的用户级配置和凭据”，不是扫描、解析或复制 `%USERPROFILE%\.codex`。

公开配置只表达能力选择：

```yaml
editorial:
  backend: deterministic  # deterministic | codex-cli
  fallback: deterministic
  timeout_seconds: 240
  allow_in_ci: false
  prompt_path: prompts/repository_summary_zh.md
  schema_path: schemas/repository_summary.schema.json
  codex_cli:
    executable: codex
    reasoning_effort_override: xhigh
```

本地完整采集可显式启用 Codex：

```powershell
python -m github_hotspots.cli run --period daily --editorial-backend codex-cli
```

对已有冻结报告刷新 README、许可证和 Owner 头像证据，并重新生成文案与海报：

```powershell
python -m github_hotspots.cli rerender reports/daily/2026-07-12.json `
  --refresh-evidence `
  --editorial-backend codex-cli
```

不加 `--refresh-evidence` 的 `rerender` 不重新请求 GitHub；适合只用报告中已有字段做离线确定性重渲染。启用 `--refresh-evidence` 会保持原排名事实不变并刷新许可证与 Owner 头像；只有同时选择 `--editorial-backend codex-cli` 时才会读取 README 供证据化编辑。

## GitHub Actions 与凭据边界

Windows 本地计划任务在每天 07:30 和周日 08:45 调用当前用户的 Codex CLI；Actions 在 09:17 和周日 10:27 使用 `deterministic` 兜底，并在同日期完整 Codex 报告与 publication history 都存在时跳过。若报告完整但 history 缺失，只修复 history，不用确定性文案覆盖 Codex 报告。GitHub-hosted runner 无法访问用户电脑上的 Codex 登录态，项目也不得通过脚本上传本机配置、认证文件、环境变量或当前会话信息。Actions 会提交公开薄历史，但不能把带完整图片的 `publish/current` 写回用户电脑。

以下内容不得进入 Git、日志、报告、Pages、测试 fixture 或 artifact：

- API key、Bearer Token、Cookie、认证头；
- 实际 endpoint、私有域名、代理地址、provider 或当前 model；
- Codex 用户级 `config.toml`、profile、认证数据库、登录缓存或 rollout；
- 包含上述信息的截图、终端录屏或原始异常响应。

未来如需在 CI 使用远程模型，必须由用户重新明确授权，并在 GitHub Settings 中手动配置专用 Secrets；不得从本机 Codex 配置自动复制。云端接入仍需保持最小权限、fork PR 隔离、日志脱敏、Schema 4.0 校验和确定性整榜回退。

## 验收清单

- [x] Prompt 4.1 / Schema 4.0 允许在 README/metadata 证据边界内做白话改写。
- [x] `one_line`、最多 5 条 `capabilities`、核心亮点、受众、前置条件、限制、许可证、README SHA、审核状态和逐字段 `evidence_ids` 均进入结构化契约。
- [x] 仓库身份、URL、语言、Star、Fork、排名、周期和增量字段全部冻结并回查。
- [x] README 被标记为不可信数据，不能触发工具、命令、文件读取或网络访问。
- [x] README 缺失时只允许单一受控候选；越界改写、非法证据 ID 或其他校验失败时整榜回退。
- [x] 许可证缺失或模糊时不猜测 MIT，也不推导商用结论。
- [x] Owner 头像经过域名、下载、像素、格式、路径和重新编码门禁；失败时安全降级。
- [x] `rerender --refresh-evidence --editorial-backend codex-cli` 可在冻结排名上刷新证据并重建发布物。
- [x] GitHub Actions 默认不调用 Codex，不复制或加载本机凭据。
- [x] 本地计划任务脚本支持独立 worktree、Codex 无回退门禁、安全 push、history 自愈与本地 `publish/current` 同步；Windows 任务注册属于显式部署步骤，不会因安装或测试自动发生。

## 官方参考

- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [Custom model providers](https://learn.chatgpt.com/docs/config-file/config-advanced#custom-model-providers)
- [Codex manual](https://learn.chatgpt.com/docs/codex-manual.md)
