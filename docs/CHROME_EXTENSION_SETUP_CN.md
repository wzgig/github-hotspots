# Codex Chrome Extension 安装、修复与替代方案

本文是一份面向 Windows 用户的操作指南，目标是在中国地区无法正常访问 Chrome 网上应用店时，安全地恢复 Codex 对现有 Chrome 标签页和登录态的访问能力。

## 当前诊断结论

诊断时间：2026-07-11。

| 检查项 | 当前状态 | 含义 |
| --- | --- | --- |
| Google Chrome | 正在运行 | 浏览器本身可用 |
| Codex Chrome Extension | 未安装 | Codex 不能控制现有 Chrome 标签页 |
| Windows Native Messaging 注册项 | 缺失 | Chrome 扩展与 Codex 桌面端之间的本机通信尚未建立 |

因此，当前不能依赖用户现有 Chrome 配置文件、登录态或已打开标签页读取网页。仅安装一个来源不明的 CRX 文件也不能解决问题，因为完整连接还需要 Codex 插件、Chrome 扩展和 native host 三部分正确配对。

> [!IMPORTANT]
> 项目自动化和维护代理不得自行创建或修改 Native Messaging 注册表项，不得伪造 native host manifest，也不得从第三方镜像下载 CRX、ZIP 或安装器。native host 应由官方 Codex/Chrome 插件安装流程注册。

## 首选安装与修复路径

### 1. 从 Codex 插件界面启动安装

1. 打开 Codex/ChatGPT Windows 桌面应用。
2. 进入 **Codex** 或 **Work**，打开 **Plugins**。
3. 如果 **Chrome** 插件已经存在但不可用，先移除它，再重新添加；如果只是关闭状态，则先启用。
4. 按插件提供的 setup flow 继续操作。官方流程会引导安装 Chrome 扩展并处理本机连接。
5. 在 Chrome 权限确认页面认真核对扩展名称和发布来源，再接受确实需要的权限。

官方扩展地址：

<https://chromewebstore.google.com/detail/codex/hehggadaopoacecdllhhajmbjkdcmajg>

优先从 Codex 插件界面进入这个地址，而不是通过搜索结果、CRX 下载站或网盘链接进入。

### 2. 中国地区无法打开官方商店时

如果官方链接因所在地区或网络环境无法访问，按以下顺序处理：

1. 仍然先在 Codex 的 **Plugins** 中执行移除后重新添加或修复，确认应用是否能完成配套组件注册。
2. 在符合当地法律、单位网络政策和个人安全要求的网络环境中访问上面的官方链接。
3. 如果仍无法获取扩展，使用 Codex 应用中的 `/feedback`，或联系 OpenAI/Codex 官方支持，询问是否有经过签名和校验的官方离线安装方案。
4. 在官方安装渠道恢复前，使用本文后面的公开网页或人工传递替代方案。

不要采用以下做法：

- 从第三方 CRX 下载器、镜像站、网盘、论坛附件或聊天群安装扩展。
- 把另一台电脑的扩展目录直接复制到当前 Chrome 配置文件。
- 使用所谓“绿色版”“破解包”或修改后的扩展绕过商店。
- 手动新建 Native Messaging 注册表键或把未知可执行文件注册为 native host。
- 为了连接扩展而关闭 Chrome 安全功能、扩大调试端口暴露范围或复用来历不明的浏览器配置文件。

这些方法既无法保证扩展更新和 native host 配对正确，也会让登录态、浏览历史、Cookie 和页面内容暴露给未知代码。

## 安装后的验证步骤

按顺序完成以下检查，前一步失败时不要继续测试登录页面。

### 1. 核查 Chrome 扩展

1. 在安装扩展的同一个 Chrome 用户配置文件中打开 `chrome://extensions`。
2. 确认 Codex 扩展存在、已启用，且扩展卡片没有错误提示。
3. 从 Chrome 工具栏的扩展菜单打开它，状态应显示 **Connected**。
4. 如果使用多个 Chrome 配置文件，确认正在测试的正是安装扩展的那个配置文件。

正常安装不需要开启 Chrome 的“开发者模式”。如扩展来源、名称或权限与官方流程不一致，应立即停止使用并卸载。

### 2. 核查 Codex 插件

1. 回到 Codex/ChatGPT 桌面应用的 **Plugins**。
2. 确认 **Chrome** 插件存在且已经开启。
3. 新建一个 Codex 任务，避免复用安装前留下的连接状态。
4. 先让 Codex 打开一个无登录、无敏感信息的公开测试页，核对页面标题和 URL。

### 3. 验证现有登录态

只有公开页测试通过后，才测试需要登录的页面：

1. 用户先在 Chrome 中手动打开目标网页，并确认当前标签页中没有不应共享的账号或隐私信息。
2. 明确授权 Codex 读取当前页面。
3. 先执行只读任务，例如读取标题、正文摘要或当前 URL，不要把发布、删除、关注、评论等写操作作为首次连接测试。
4. 核对 Codex 返回的信息确实来自当前标签页，而不是公开搜索结果或另一个浏览器配置文件。

### 4. Native Messaging 的只读核查

如需确认 Windows 是否存在 Native Messaging host，可在 PowerShell 中执行只读检查：

```powershell
Get-ChildItem 'HKCU:\Software\Google\Chrome\NativeMessagingHosts' -ErrorAction SilentlyContinue
Get-ChildItem 'HKLM:\Software\Google\Chrome\NativeMessagingHosts' -ErrorAction SilentlyContinue
```

这两条命令只列出现有子项。不要根据网上示例手工补建键值；注册项缺失时，应返回 Codex **Plugins** 重新执行官方安装流程。

## 常见故障处理

| 现象 | 安全处理方式 |
| --- | --- |
| `chrome://extensions` 中没有 Codex | 从 Codex **Plugins** 重新添加 Chrome 插件并按官方流程安装 |
| 扩展提示 `Disconnected` 或 `missing native host` | 移除并重新添加 Codex 的 Chrome 插件，重新走 setup flow；不要手改注册表 |
| 扩展存在但 Codex 插件关闭 | 在 Codex/Work 的 **Plugins** 中启用 Chrome |
| 多个 Chrome 配置文件中只有一个可用 | 切换到已安装扩展的配置文件，或通过官方流程在目标配置文件安装 |
| 扩展显示 `Connected`，但任务仍不可用 | 新建任务，重启 Chrome 和桌面应用后重试 |
| 重装后仍然无法连接 | 使用 `/feedback` 并保留任务 ID、扩展状态截图和非敏感诊断信息联系官方支持 |
| Chrome 显示“由贵单位管理” | 查看 `chrome://management` 和 `chrome://policy`，由单位管理员批准扩展与 native messaging；不要绕过管理策略 |

## 无法安装扩展时的替代方案

### 公开网页

对于不依赖登录态的 GitHub、项目官网和公开文章，优先使用：

- Codex 内置 Browser。它使用与日常 Chrome 分离的浏览器配置文件，不会自动继承 Chrome 登录态。
- Playwright 或普通 HTTP 请求读取公开、允许访问的页面。
- GitHub REST/GraphQL API 获取仓库事实数据。本项目的 GitHub 热点流程应继续以官方 API、GitHub Trending 和本地快照为主。

公开网页仍可能因 JavaScript 渲染、地区限制、登录墙、验证码或反自动化策略而只能读取部分内容。不得绕过验证码、登录限制或网站访问控制。

### 登录后网页

在 Chrome 扩展恢复前，采用人工在环方式：

1. 用户在自己的 Chrome 中打开目标页面。
2. 将允许处理的正文复制为文本，或导出为 PDF、保存网页截图后交给 Codex。
3. 对长页面可分段截图，并保留页面标题、发布日期和原始链接，方便核对上下文。
4. 涉及账号、私信、订单、Cookie、二维码或个人资料时，先遮盖无关敏感信息。

也可以在 Codex 内置 Browser 的独立配置文件中由用户自行登录，但它不会复用现有 Chrome 会话。是否登录应由用户明确决定，且首次使用只进行只读验证。

### 小红书页面的项目边界

- 可以查看用户提供的公开链接并总结当前能正常呈现的公开内容。
- 登录墙、折叠正文、完整评论、收藏列表等内容可能需要用户现有登录态或人工提供截图。
- 不绕过验证码、登录验证、频率限制或反爬机制，不批量抓取账号内容。
- 小红书仅用于理解内容呈现方式；GitHub 热点数据仍从 GitHub 官方来源取得。

## 安全检查清单

- [ ] 扩展来自官方 Codex 插件流程或上面的官方 Chrome 网上应用店链接。
- [ ] 未安装第三方 CRX、ZIP、镜像包或未知 native host。
- [ ] `chrome://extensions` 中扩展已启用且无错误。
- [ ] 扩展工具栏状态显示 **Connected**。
- [ ] Codex/Work 的 Chrome 插件已开启。
- [ ] 使用的是安装扩展的同一个 Chrome 配置文件。
- [ ] 已先用无登录公开页完成只读测试。
- [ ] 登录页面的读取由用户明确授权，且未暴露无关敏感数据。

## 官方参考

- [Chrome extension setup and troubleshooting](https://learn.chatgpt.com/docs/chrome-extension)
- [Built-in browser](https://learn.chatgpt.com/docs/browser?surface=app)
- [Codex manual](https://developers.openai.com/codex/codex-manual.md)
