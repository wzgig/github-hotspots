# 本地 Codex 模型能力接入与密钥隔离方案

本文定义 GitHub Hotspots 项目未来接入 LLM 摘要能力时的安全边界。目标是在本地复用当前 Codex 已经配置好的模型提供方和凭据，同时确保公开 GitHub 仓库、日志和 GitHub Actions 不包含实际 endpoint、API key 或 model 标识。

## 决策摘要

当前本机 Codex 使用自定义的、与 Responses API 兼容的模型提供方。项目不需要改用 OpenAI 官网 API，也不应读取、复制或公开 Codex 的实际连接配置。

推荐方案如下：

1. **GitHub Actions 默认继续使用确定性摘要器**，不依赖 LLM，也不需要任何模型密钥。
2. **本地可选使用 `codex exec` 适配器**。项目只调用 Codex CLI，由 CLI 自己加载用户级配置和凭据。
3. **未来如需在 CI 在线生成摘要**，必须由用户显式启用，并在 GitHub 仓库设置中手动配置 Secrets。
4. **禁止自动同步本机 Codex 配置或密钥到 GitHub**，也禁止把真实 endpoint、key、model 写入文档、示例配置、提交记录或运行产物。

## 推荐架构

```text
GitHub 仓库公共数据 / 本地快照
              |
              v
       事实约束与输入校验
              |
       +------+------------------+
       |                         |
       v                         v
确定性摘要器（默认）       Codex CLI 适配器（仅本地可选）
       |                         |
       |                  codex exec
       |                         |
       |             用户级 Codex 配置与凭据
       |                         |
       +------------+------------+
                    v
          JSON Schema 与事实回查
                    |
                    v
            Markdown / 小红书文案
```

项目代码只知道“调用 `codex exec` 并接收结构化结果”，不知道实际服务地址、密钥或模型名称。这样即使仓库公开，其他人也只能看到适配器接口，不能得到用户的本机连接信息。

## 为什么优先使用 `codex exec`

Codex CLI 的非交互模式适合脚本调用，并可直接复用当前用户已经配置的 provider 和认证状态。与项目直接解析本地配置相比，它具有以下优势：

- 项目无需读取 `%USERPROFILE%\.codex\config.toml` 或任何认证文件。
- 项目无需知道 provider 的 endpoint、环境变量名、API key 或 model。
- 可以使用 `--output-schema` 强制最终响应满足 JSON Schema。
- 可以使用 `--ephemeral` 避免保存本次会话 rollout 文件。
- 可以使用 `--sandbox read-only` 限制模型生成命令的文件写权限。
- 更换本机 provider 时，项目适配器通常不需要修改。

> [!IMPORTANT]
> “读取本地 Codex 使用的 API”在本项目中应理解为“调用本机 Codex CLI，让 CLI 复用自己的用户级配置和凭据”，而不是让项目扫描、解析或复制 Codex 的配置文件和认证存储。

## 本地调用约定

建议未来实现 `CodexCliSummarizer`，并遵守以下调用约定：

- 输入仅包含已经采集并校验的公开 GitHub 仓库事实。
- README、description、topics 等外部文本一律视为不可信数据，不执行其中的指令。
- 在临时工作目录中运行，目录只放本次所需的提示词、证据 JSON 和输出 Schema。
- 使用参数数组启动子进程，不使用 `shell=True`，不拼接可执行的命令字符串。
- 使用 `--ephemeral`、`--sandbox read-only` 和 `--output-schema`。
- 不传 `--model`，不在仓库中固定或记录用户当前模型。
- 不使用 `--ignore-user-config`，因为本地 provider 选择位于用户级配置中。
- 不使用 `--dangerously-bypass-approvals-and-sandbox`。
- 设置超时；CLI 不存在、超时、返回非零、输出无法解析或事实校验失败时，自动回退到确定性摘要器。

PowerShell 原型如下。`$StagingDir` 应是程序为单次摘要创建的临时目录，`$SchemaPath` 应指向仓库未来提供的公开 JSON Schema；其中不得包含任何凭据。

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
    -C $StagingDir `
    --output-schema $SchemaPath `
    --output-last-message $OutputPath `
    -
```

适配器完成调用后仍必须在程序侧执行：

1. JSON 解析和 Schema 校验。
2. `repository_id`、`full_name`、URL、语言、Star、Fork 和增量数字的逐字段回查。
3. 字段长度、亮点条数和必填字段检查。
4. 检查输出中是否出现输入之外的仓库、链接、数字或来源。
5. 校验失败时丢弃 LLM 结果并使用确定性摘要，不能“尽量修补”未知事实。

## 建议的项目配置接口

公开配置只表达能力选择，不表达 provider 细节：

```yaml
summarizer:
  backend: deterministic  # deterministic | codex-cli | remote
  fallback: deterministic
  timeout_seconds: 120
```

建议语义：

| `backend` | 使用场景 | 凭据来源 |
| --- | --- | --- |
| `deterministic` | 本地与 GitHub Actions 默认值 | 无 |
| `codex-cli` | 用户主动启用的本地摘要 | Codex CLI 自行加载用户级配置 |
| `remote` | 用户显式配置后的受信任 CI | GitHub Secrets |

任何提交到公开仓库的报告只能记录以下非敏感运行信息：

- 摘要后端类型，例如 `deterministic` 或 `codex-cli`。
- 提示词版本、Schema 版本和校验结果。
- 耗时、是否回退、错误类别和脱敏后的错误摘要。

不得记录实际 provider 名称、endpoint、API key、认证头、model、完整请求头、原始错误响应或用户级 Codex 配置路径内容。

## GitHub Actions 策略

### 默认策略

公开仓库的每日和每周工作流默认使用确定性摘要器。这样能够：

- 在没有模型服务时仍稳定生成榜单。
- 避免 fork、依赖脚本或第三方 Action 接触模型密钥。
- 保证同一输入得到可审计、可回放的输出。
- 避免把本机的自定义 provider 配置错误地复制到云端 runner。

本机 Codex 登录态、用户级配置和凭据不会自动出现在 GitHub-hosted runner 中，也不应通过脚本上传。

### 未来显式启用在线摘要

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
- 在线摘要失败时回退到确定性摘要，并让核心榜单任务继续完成。

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

- 发送给模型的内容以公开 GitHub 元数据和必要的 README 摘要为限。
- 不发送 Codex 配置、系统环境变量、个人目录内容或无关仓库文件。
- 提示词必须说明外部仓库文本是不可信数据，禁止执行其中嵌入的命令或指令。
- 本地适配器在独立临时目录运行，避免模型主动读取整个项目或其他本机目录。
- 子进程日志必须脱敏；不得把完整环境、请求头或认证失败响应写入报告。
- 输出通过 Schema 和事实回查后才能进入公开 Markdown 或 JSON。
- 每次模型集成变更都要在项目日志中说明接口、验证和回退行为，但不披露 provider 细节。

## 实施顺序

1. 保持当前确定性摘要器为唯一默认实现。
2. 增加公开的摘要输出 JSON Schema 和固定测试样本。
3. 实现 `CodexCliSummarizer`，只支持本地显式启用。
4. 增加超时、非零退出、非法 JSON、事实漂移和 CLI 不存在的回退测试。
5. 用不含敏感信息的公开仓库样本完成端到端验证。
6. 观察一段时间后，再由用户决定是否需要 `remote` 后端和 GitHub Secrets。

## 验收清单

- [ ] 不配置任何 LLM 时，日榜和周榜仍可完整生成。
- [ ] `codex-cli` 后端不解析 Codex 用户级配置或认证文件。
- [ ] 仓库中不存在实际 endpoint、key、model 或认证头。
- [ ] 本地调用使用临时目录、只读沙箱、临时会话和 JSON Schema。
- [ ] 模型结果中的数字、URL 和仓库标识全部经过事实回查。
- [ ] CLI 缺失、超时、失败或输出不合规时自动使用确定性摘要。
- [ ] GitHub Actions 默认不加载任何 Codex 或 LLM 凭据。
- [ ] CI 在线摘要只有在用户手动配置 GitHub Secrets 后才能启用。
- [ ] Secrets 不会暴露给 fork PR、不受信任脚本或公开 artifact。

## 官方参考

- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [Custom model providers](https://learn.chatgpt.com/docs/config-file/config-advanced#custom-model-providers)
- [Codex manual](https://developers.openai.com/codex/codex-manual.md)
