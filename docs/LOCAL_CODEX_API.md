# 本地 Codex 受控选稿与密钥隔离方案

本文定义 GitHub Hotspots 可选调用本地 Codex CLI 时的使用时机、接口约定和安全边界。Codex Schema 3.0 的角色是“整榜叙事规划器和受控选稿器”：程序先为每个仓库生成 7 个完整、确定性的候选版本，Codex 只能选择其中一个并逐字符复制。候选、事实、排名和最终文字都不由模型自由生成，公开仓库、日志和 GitHub Actions 也不包含实际 endpoint、API key 或 model 标识。

## 决策摘要

项目不需要改用 OpenAI 官网 API，也不应读取、复制或公开 Codex 的实际连接配置。本地调用只面向已经安装并由用户自行配置的 `codex` 命令。

推荐方案如下：

1. **GitHub Actions 默认继续使用确定性候选生成和选稿**，不依赖 LLM，也不需要任何模型密钥。
2. **本地可选使用 `codex exec` 受控选稿适配器**。项目只调用 Codex CLI，由 CLI 自己加载用户级配置和凭据；调用发生在 GitHub 事实、两榜排名和 7 个候选版本全部冻结之后。
3. **未来如需在 CI 在线选稿**，必须由用户显式启用，并在 GitHub 仓库设置中手动配置 Secrets。
4. **禁止自动同步本机 Codex 配置或密钥到 GitHub**，也禁止把真实 endpoint、key、model 写入文档、示例配置、提交记录或运行产物。

## 当前实施状态（2026-07-12）

- 确定性候选生成与确定性选稿仍是已经运行的默认路径，GitHub Actions 不调用本地 Codex。
- `summarizer.py` 为每个仓库生成定位、增长、技术栈、规模、Topics、活跃度和来源 7 个候选；自然度与项目差异主要通过改进这套候选库获得。
- `editorial.py` 已实现 Schema 3.0 整榜选稿、候选逐字符匹配、角度覆盖、数字/URL/身份回查、CI 禁用和整榜回退。
- Schema 3.0 已使用冻结日榜与周榜的综合/AI 四个榜单完成真实本地结构化受控选稿验证；四个批次均为 `used_backend=codex-cli`、`fallback_used=false`。旧版自由改写契约的历史冒烟不计入本次验收。
- 当前用户级配置中的 reasoning 值超出已安装 CLI 0.124.0 的枚举。项目没有修改全局配置，而是在公开项目配置中只覆盖为受支持的 `xhigh`；provider 和凭据仍由 Codex CLI 自行加载。
- GitHub Actions 默认继续使用 `deterministic`，不会尝试访问用户电脑、本地 provider 或凭据。

## 何时使用本地 Codex

本地 Codex 只在以下顺序的第 7 步介入：

```text
1. GitHub 候选发现
2. API 事实补全与过滤
3. 快照和增量计算
4. 综合主榜 / AI 专题榜独立排名
5. 冻结仓库身份、URL、数字、榜单和证据
6. 每个仓库生成 7 个确定性候选
7. 可选 Codex 整榜规划角度并选择候选
8. Schema、事实与候选逐字符回查
9. 文案 / 海报文字 / 人工审核包
```

Codex 只适合处理以下选择任务：

- 查看整榜的 7 类候选，为相邻项目分配不同角度。
- 选择最能体现仓库差异的完整候选，并在周榜中覆盖全部 7 个角度。
- 把所选候选的 `one_line`、三条 `highlights` 和 `audience` 逐字符复制到结构化输出。
- 回报选中的角度、固定证据引用和批次质量字段，供程序再次校验。

不得交给 Codex 的工作包括：自由改写、翻译、压缩、润色、候选拼接、仓库搜索、AI 专题分类、排名、Star/Fork/日期计算、URL 补全、许可证推断或任何 GitHub 数字事实修改。若文案仍显得同质化，应先改进确定性候选库和受众规则，而不是扩大模型生成权限。

## 推荐架构

```text
GitHub 仓库公共数据 / 本地快照
              |
              v
       事实冻结与输入校验
              |
              v
        生成 7 类确定性候选
              |
       +------+------------------+
       |                         |
       v                         v
  确定性选稿（默认）       Codex CLI 受控选稿（本地可选）
       |                         |
       |                  codex exec
       |                         |
       |             用户级 Codex 配置与凭据
       |                         |
       +------------+------------+
                    v
     JSON Schema、事实与候选逐字符回查
                    |
                    v
      Markdown / 小红书文案 / 海报短句
```

项目代码只知道“调用 `codex exec` 并接收受控选择结果”，不知道实际服务地址、密钥或模型名称。这样即使仓库公开，其他人也只能看到适配器接口，不能得到用户的本机连接信息。

## 为什么优先使用 `codex exec`

Codex CLI 的非交互模式适合脚本调用，并可直接复用当前用户已经配置的 provider 和认证状态。与项目直接解析本地配置相比，它具有以下优势：

- 项目无需读取 `%USERPROFILE%\.codex\config.toml` 或任何认证文件。
- 项目无需知道 provider 的 endpoint、环境变量名、API key 或 model。
- 可以使用 `--output-schema` 强制最终响应满足 JSON Schema。
- 可以使用 `--ephemeral` 避免保存本次会话 rollout 文件。
- 可以使用 `--sandbox read-only` 阻止调用过程修改工作区文件。
- 更换本机 provider 时，项目适配器通常不需要修改。

> [!IMPORTANT]
> “读取本地 Codex 使用的 API”在本项目中应理解为“调用本机 Codex CLI，让 CLI 复用自己的用户级配置和凭据”，而不是让项目扫描、解析或复制 Codex 的配置文件和认证存储。

## 本地调用约定

本次升级的适配器以整榜批处理方式工作，并遵守以下调用约定：

- 输入仅包含已经采集并校验的公开 GitHub 仓库事实、冻结后的榜单顺序，以及程序生成的 7 个 `candidate_summaries`。
- 一次调用处理完整榜单。模型先规划互不重复的编辑角度，再从每个仓库的候选中选择一个完整版本；它不逐项写作。
- README、description、topics 等外部文本一律视为不可信数据，不执行其中的指令。
- 在临时工作目录中运行；提示词与证据通过 stdin 提交，目录只保留本次输出 Schema 和临时结果。
- 使用参数数组启动子进程，不使用 `shell=True`，不拼接可执行的命令字符串。
- 使用 `--ephemeral`、`--sandbox read-only`、`--ignore-rules` 和 `--output-schema`；显式清空 MCP server，并禁用 shell、浏览器、插件、工具搜索、多代理和其他与文本选稿无关的功能。
- 不传 `--model`，不在仓库中固定或记录用户当前模型。
- 不使用 `--ignore-user-config`，因为本地 provider 选择位于用户级配置中。
- 不使用 `--dangerously-bypass-approvals-and-sandbox`。
- 设置超时；CLI 不存在、超时、返回非零、输出无法解析、候选不匹配或事实校验失败时，自动回退到确定性选稿。

整榜结构化输出至少要包含每个仓库的 `repository_id`、所选角度、短定位、三条要点、适用人群及证据映射。短定位、要点和适用人群必须全部来自同一个候选，并与输入逐字符相等。模型不得增删仓库、改变榜单归属、改动顺序或拼接两个候选。

PowerShell 接口原型如下。`$StagingDir` 应是程序为单次选稿创建的临时目录，`$SchemaPath` 指向公开的 `schemas/repository_summary.schema.json`；其中不得包含任何凭据。日常使用应通过项目 CLI，而不是手工拼接这段命令。

```powershell
$prompt = Get-Content $PromptPath -Raw
$evidence = Get-Content $EvidencePath -Raw

@"
$prompt

<repository_evidence>
$evidence
</repository_evidence>
"@ | codex exec `
    --ephemeral `
    --sandbox read-only `
    --skip-git-repo-check `
    --ignore-rules `
    --color never `
    -C $StagingDir `
    -c 'shell_environment_policy.inherit="none"' `
    -c 'mcp_servers={}' `
    --output-schema $SchemaPath `
    --output-last-message $OutputPath `
    -
```

适配器完成调用后仍必须在程序侧执行：

1. JSON 解析和 Schema 校验。
2. `repository_id`、`full_name`、URL、语言、Star、Fork 和增量数字的逐字段回查。
3. 验证 `one_line`、三条 `highlights` 和 `audience` 与同一个候选逐字符相等。
4. 验证日榜角度不重复，周榜覆盖 7 个角度，相邻项目不复用角度。
5. 检查输出中是否出现输入之外的仓库、链接、数字、文字或来源。
6. 执行榜内重复与禁用套话检查。
7. 校验失败时丢弃整榜结果并使用确定性选稿，不能“尽量修补”模型输出。

## 项目配置接口

公开配置只表达能力选择，不表达 provider 细节：

```yaml
editorial:
  backend: deterministic  # deterministic | codex-cli
  fallback: deterministic
  timeout_seconds: 120
  allow_in_ci: false
  prompt_path: prompts/repository_summary_zh.md
  schema_path: schemas/repository_summary.schema.json
  codex_cli:
    executable: codex
    reasoning_effort_override: xhigh
```

建议语义：

| `backend` | 使用场景 | 凭据来源 |
| --- | --- | --- |
| `deterministic` | 本地与 GitHub Actions 默认的候选生成和选稿 | 无 |
| `codex-cli` | 用户主动启用的本地整榜受控选稿 | Codex CLI 自行加载用户级配置 |
| `remote`（未来） | 用户显式授权并实现远程受控选稿适配器后的受信任 CI | GitHub Secrets |

本地显式启用可以运行完整采集，也可以只重渲染冻结报告。后者不会重新访问 GitHub，更适合文案与海报审核：

```powershell
python -m github_hotspots.cli run --period daily --editorial-backend codex-cli
python -m github_hotspots.cli rerender reports/daily/2026-07-11.json --editorial-backend codex-cli
```

Schema 3.0 的真实 `rerender` 验证已经覆盖冻结日榜与周榜的综合/AI 四个榜单，均使用 `codex-cli` 且未回退。任何后续运行若遇到 CLI、用户配置、超时、候选不匹配或其他输出校验问题，都必须整榜回退到 `deterministic`。

任何提交到公开仓库的报告只能记录以下非敏感运行信息：

- 选稿后端类型，例如 `deterministic` 或 `codex-cli`。
- 提示词版本、Schema 版本和校验结果。
- 耗时、是否回退、错误类别和脱敏后的错误摘要。

不得记录实际 provider 名称、endpoint、API key、认证头、model、完整请求头、原始错误响应或用户级 Codex 配置路径内容。

## GitHub Actions 策略

### 默认策略

公开仓库的每日和每周工作流默认使用确定性候选生成和选稿。海报也由代码确定性渲染，不依赖模型生成图片。这样能够：

- 在没有模型服务时仍稳定生成榜单。
- 避免 fork、依赖脚本或第三方 Action 接触模型密钥。
- 保证同一输入得到可审计、可回放的输出。
- 避免把本机的自定义 provider 配置错误地复制到云端 runner。

本机 Codex 登录态、用户级配置和凭据不会自动出现在 GitHub-hosted runner 中，也不应通过脚本上传。

### 未来显式启用在线选稿

只有用户确认需要后，才增加 `remote` 后端和对应工作流。届时由用户在 GitHub 仓库 **Settings > Secrets and variables > Actions** 中手动创建 Secrets，例如：

- `HOTSPOTS_LLM_API_KEY`
- `HOTSPOTS_LLM_BASE_URL`
- `HOTSPOTS_LLM_MODEL`

这些名称只是公开接口，不包含任何真实值。工作流必须满足：

- Secrets 仅注入执行模型调用的单个步骤，不设置为整个 job 的环境变量。
- 不在 `pull_request`、来自 fork 的工作流或其他不受信任事件中使用 Secrets。
- 不运行会输出环境变量、HTTP 请求头或完整异常对象的调试命令。
- 不把原始模型响应、网络追踪或含请求头的日志上传为公开 artifact。
- 可使用受保护 Environment 和人工审批限制谁能启动带密钥的任务。
- 在线选稿失败时回退到确定性选稿，并让核心榜单任务继续完成。

> [!WARNING]
> 禁止工作流读取并上传 `%USERPROFILE%\.codex\config.toml`、认证文件、profile 文件或本机环境变量。也禁止让自动化从当前 Codex 会话中“提取”endpoint、key 或 model 后创建 GitHub Secrets。Secrets 必须由用户在 GitHub 设置中显式配置。

## 公开仓库的密钥防护边界

以下内容不得进入 Git：

- 真实 API key、bearer token、Cookie 或认证头。
- 实际模型 endpoint、内网域名、代理地址或 provider 标识。
- 本机正在使用的实际 model 名称。
- Codex 用户级 `config.toml`、profile、认证数据库或登录缓存。
- 包含上述信息的截图、终端录屏、Issue、日志、测试 fixture 或报告。

`.env.example` 只能保留空值或明显的占位符；真实 `.env` 必须继续由 `.gitignore` 排除。提交前应检查暂存差异、未跟踪文件和工作流输出，发现疑似凭据时先停止提交并轮换相关密钥。

## 数据与安全要求

- 发送给模型的内容以公开 GitHub 元数据、冻结排名和 7 个确定性候选为限。
- 不发送 Codex 配置、系统环境变量、个人目录内容或无关仓库文件。
- 提示词必须说明外部仓库文本是不可信数据，禁止执行其中嵌入的命令或指令。
- 本地适配器在独立临时目录运行，避免模型主动读取整个项目或其他本机目录。
- 子进程日志必须脱敏；不得把完整环境、请求头或认证失败响应写入报告。
- 输出通过 Schema、事实回查和候选逐字符匹配后才能进入公开 Markdown 或 JSON。
- 每次模型集成变更都要在项目日志中说明接口、验证和回退行为，但不披露 provider 细节。

## 当前实现与后续验证

1. 已保持确定性候选生成和确定性选稿为唯一默认路径。
2. 已实现 Schema 3.0、7 类候选、整榜 `codex-cli` 受控选稿和候选逐字符回查。
3. 已覆盖 CLI 缺失、超时、非零退出、非法 JSON、事实漂移、候选不匹配和整榜回退测试。
4. 已用不含敏感信息的冻结公开仓库样本完成 Schema 3.0 端到端验证；日榜与周榜的综合/AI 四个批次均未回退。
5. 固定评估集应继续衡量候选库本身的自然度、差异度和适用人群准确性；Codex 只衡量角度分配、候选选择、延迟和回退率。
6. 观察一段时间后，再由用户决定是否需要 `remote` 后端和 GitHub Secrets。

## 验收清单

- [x] 不配置任何 LLM 时，日榜和周榜仍可完整生成。
- [x] `codex-cli` 后端不解析 Codex 用户级配置或认证文件。
- [x] 仓库中不存在实际 endpoint、key、model 或认证头。
- [x] 本地调用使用临时目录、只读沙箱、临时会话和 JSON Schema。
- [x] 模型结果中的数字、URL 和仓库标识全部经过事实回查。
- [x] 每个自然语言字段都必须与同一个 `candidate_summaries` 候选逐字符相等。
- [x] 模型按整榜处理并通过角度覆盖、相邻角度和禁用套话检查。
- [x] CLI 缺失、超时、失败或输出不合规时自动使用确定性选稿。
- [x] GitHub Actions 默认不加载任何 Codex 或 LLM 凭据。
- [x] 使用冻结公开样本完成日榜与周榜综合/AI 四个批次的真实 Schema 3.0 本地结构化验证。
- [ ] CI 在线选稿只有在用户手动配置 GitHub Secrets 后才能启用。
- [ ] Secrets 不会暴露给 fork PR、不受信任脚本或公开 artifact。

## 官方参考

- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [Custom model providers](https://learn.chatgpt.com/docs/config-file/config-advanced#custom-model-providers)
- [Codex manual](https://learn.chatgpt.com/docs/codex-manual.md)
