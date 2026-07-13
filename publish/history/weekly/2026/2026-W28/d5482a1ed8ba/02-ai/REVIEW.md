# W001-A · AI 专题榜 发布审核

- 状态：`draft`
- 编辑后端：`codex-cli`
- 回退：`false`

## 标题

GitHub AI周报第1期｜7个AI项目值得收藏

## 可粘贴正文

2026-07-12 · AI 专题榜 · 第1期

GitHub Hotspots AI 周报第1期。去掉术语包装，用 7 张项目卡讲清实际能力、适用人群和上手前提。

先看结论：
01｜asgeirtj/system_prompts_leaks：按厂商、产品和版本归档 AI 系统提示词，方便检索指令结构并对照不同实现
02｜iOfficeAI/OfficeCLI：用单个命令行程序创建、读取和修改办公文档，并为脚本或 AI Agent 提供结构化操作接口
03｜usestrix/strix：让多个 AI 渗透测试 Agent 动态运行目标、验证漏洞，并输出复现线索、修复建议和报告
04｜Zackriya-Solutions/meetily：在本机捕获并实时转写会议，再用可选模型生成摘要，避免把录音和转写内容发送到云端
05｜ogulcancelik/herdr：把多个编程 Agent 放进终端分屏中统一查看、切换和恢复，并让 Agent 通过接口互相等待或创建面板
06｜stablyai/orca：在隔离的 Git 工作树中并行运行多个命令行编程 Agent，并集中查看终端、代码差异和任务状态
07｜diegosouzapw/OmniRoute：在本机提供统一模型接口，把编程工具请求路由到不同供应商，并在额度或连接失败时切换后备模型

下周想看我深挖哪一个的真实使用门槛？

AI 辅助整理｜人工发布

#GitHub #开源项目 #AI #AI工具

## 项目事实

### 01｜asgeirtj/system_prompts_leaks

- 仓库：https://github.com/asgeirtj/system_prompts_leaks
- 定位：按厂商、产品和版本归档 AI 系统提示词，方便检索指令结构并对照不同实现
- Star：56,147
- Fork：9,269
- 本期信号：+7,765 Star（trending）
- 许可证：CC0-1.0
- 能力：检索不同厂商与模型的系统提示词；对照同一产品不同版本的指令变化；查看编程助手、搜索和办公集成提示词；查阅工具定义、策略与原始提示词资料；定位近期更新的提示词条目

### 02｜iOfficeAI/OfficeCLI

- 仓库：https://github.com/iOfficeAI/OfficeCLI
- 定位：用单个命令行程序创建、读取和修改办公文档，并为脚本或 AI Agent 提供结构化操作接口
- Star：15,014
- Fork：1,022
- 本期信号：+5,789 Star（trending）
- 许可证：Apache-2.0
- 能力：创建并编辑三类常见办公文档；读取文本、结构、样式、公式与图表；渲染 HTML、PNG 和实时浏览器预览；合并模板占位符与结构化数据；批量执行操作并输出结构化结果

### 03｜usestrix/strix

- 仓库：https://github.com/usestrix/strix
- 定位：让多个 AI 渗透测试 Agent 动态运行目标、验证漏洞，并输出复现线索、修复建议和报告
- Star：40,480
- Fork：4,256
- 本期信号：+6,443 Star（trending）
- 许可证：Apache-2.0
- 能力：扫描本地代码、代码仓库或 Web 应用；验证访问控制、注入与业务逻辑漏洞；协调多个 Agent 并行完成渗透测试；输出漏洞复现步骤与修复建议；接入持续集成检查代码变更

### 04｜Zackriya-Solutions/meetily

- 仓库：https://github.com/Zackriya-Solutions/meetily
- 定位：在本机捕获并实时转写会议，再用可选模型生成摘要，避免把录音和转写内容发送到云端
- Star：23,105
- Fork：2,431
- 本期信号：+8,795 Star（trending）
- 许可证：MIT
- 能力：捕获会议并实时生成文字记录；使用 Whisper 或 Parakeet 本地转写；导入已有音频生成或增强转写；选择本地或外部模型生成会议摘要；在本地保存录音、模型和转写内容

### 05｜ogulcancelik/herdr

- 仓库：https://github.com/ogulcancelik/herdr
- 定位：把多个编程 Agent 放进终端分屏中统一查看、切换和恢复，并让 Agent 通过接口互相等待或创建面板
- Star：15,460
- Fork：1,035
- 本期信号：+4,714 Star（trending）
- 许可证：AGPL-3.0-or-later
- 能力：查看 Agent 的阻塞、工作与完成状态；拆分并拖动多个真实终端面板；分离后从其他终端或 SSH 重新连接；让 Agent 创建面板并读取其他任务输出；通过插件扩展面板与终端工作流

### 06｜stablyai/orca

- 仓库：https://github.com/stablyai/orca
- 定位：在隔离的 Git 工作树中并行运行多个命令行编程 Agent，并集中查看终端、代码差异和任务状态
- Star：16,306
- Fork：1,274
- 本期信号：+4,328 Star（trending）
- 许可证：MIT
- 能力：把同一任务分发给多个独立 Agent；比较各工作树结果并合并选定方案；在代码差异行上批注并反馈给 Agent；连接远程主机运行 Agent 与终端；从手机监控任务并继续发送指令

### 07｜diegosouzapw/OmniRoute

- 仓库：https://github.com/diegosouzapw/OmniRoute
- 定位：在本机提供统一模型接口，把编程工具请求路由到不同供应商，并在额度或连接失败时切换后备模型
- Star：15,598
- Fork：2,366
- 本期信号：+4,268 Star（trending）
- 许可证：MIT
- 能力：把不同客户端协议转换为统一接口；组合多个模型并配置路由策略；监测连接状态并跳过故障目标；压缩输入和工具输出以减少令牌占用；通过 MCP 或 A2A 暴露网关操作

## 配图顺序

01. `images/01-cover.png` — 封面
02. `images/02-rank-01-asgeirtj-system-prompts-leaks.png` — asgeirtj/system_prompts_leaks
03. `images/03-rank-02-iofficeai-officecli.png` — iOfficeAI/OfficeCLI
04. `images/04-rank-03-usestrix-strix.png` — usestrix/strix
05. `images/05-rank-04-zackriya-solutions-meetily.png` — Zackriya-Solutions/meetily
06. `images/06-rank-05-ogulcancelik-herdr.png` — ogulcancelik/herdr
07. `images/07-rank-06-stablyai-orca.png` — stablyai/orca
08. `images/08-rank-07-diegosouzapw-omniroute.png` — diegosouzapw/OmniRoute

## 人工确认

- [ ] 标题和正文已复核
- [ ] 项目事实已复核
- [ ] 图片顺序已复核
- [ ] 发布后填写平台链接
