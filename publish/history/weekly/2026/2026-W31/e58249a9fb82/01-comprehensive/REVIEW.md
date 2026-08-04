# W004-C · 综合主榜 发布审核

- 状态：`draft`
- 编辑后端：`codex-cli`
- 回退：`false`

## 标题

GitHub周报第4期｜7个开源项目值得收藏

## 可粘贴正文

2026-08-02 · 综合主榜 · 第4期

GitHub Hotspots 周报第4期。把这一周的 7 个热点压缩成一组可收藏的项目卡：先看用途，再看为什么值得关注。

先看结论：
01｜block/buzz：让人类与 AI 代理在自托管协作空间里共同讨论、改代码、跑流程，并保留统一审计记录
02｜permissionlesstech/bitchat：在断网时通过蓝牙网状网络聊天，联网后再借助 Nostr 中继扩展到远距离通信
03｜mattpocock/skills：把需求澄清、测试驱动、故障诊断和代码评审整理成可组合的编码代理工作流
04｜diegosouzapw/OmniRoute：把多个模型供应商接到同一个兼容接口，并按额度、成本、延迟或故障情况自动切换路线
05｜alibaba/open-code-review：读取代码差异并结合仓库上下文生成精确到行的审查意见，也能扫描没有有效差异的完整文件
06｜citrolabs/ego-lite：让外部 AI 代理在独立浏览空间里复用你的登录状态执行网页任务，同时不占用正在操作的标签页
07｜1jehuang/jcode：在终端里运行可记忆、可并行协作的编码代理，并统一接入多种模型、MCP 工具与浏览器操作

这一周你最想把哪一个加入收藏夹？

AI 辅助整理｜人工发布

#GitHub #开源项目 #程序员 #开发者工具

## 项目事实

### 01｜block/buzz

- 仓库：https://github.com/block/buzz
- 定位：让人类与 AI 代理在自托管协作空间里共同讨论、改代码、跑流程，并保留统一审计记录
- Star：20,584
- Fork：2,172
- 本期信号：+8,615 Star（snapshot）
- 许可证：Apache-2.0
- 能力：搜索历史对话并附上相关讨论依据；接收补丁并在频道中组织代码评审；触发消息、定时或 Webhook 工作流；集中检索对话、Git 事件和审批记录；让多个代理创建频道、画布和协作流程

### 02｜permissionlesstech/bitchat

- 仓库：https://github.com/permissionlesstech/bitchat
- 定位：在断网时通过蓝牙网状网络聊天，联网后再借助 Nostr 中继扩展到远距离通信
- Star：34,004
- Fork：5,423
- 本期信号：+5,270 Star（snapshot）
- 许可证：Unlicense
- 能力：发现附近设备并建立蓝牙网状连接；通过周边设备多跳转发本地消息；自动选择蓝牙或 Nostr 发送私信；按地理坐标进入不同范围的地域频道；三击执行紧急清除本机数据

### 03｜mattpocock/skills

- 仓库：https://github.com/mattpocock/skills
- 定位：把需求澄清、测试驱动、故障诊断和代码评审整理成可组合的编码代理工作流
- Star：199,159
- Fork：17,165
- 本期信号：+10,615 Star（snapshot）
- 许可证：MIT
- 能力：追问需求并补齐尚未决定的设计分支；建立项目术语表与架构决策记录；按红绿重构循环实现功能或修复缺陷；复现并缩小疑难故障后再验证修复；分别检查代码规范与需求实现偏差

### 04｜diegosouzapw/OmniRoute

- 仓库：https://github.com/diegosouzapw/OmniRoute
- 定位：把多个模型供应商接到同一个兼容接口，并按额度、成本、延迟或故障情况自动切换路线
- Star：37,213
- Fork：4,820
- 本期信号：+7,015 Star（snapshot）
- 许可证：MIT
- 能力：接入兼容 OpenAI 接口的模型工具；按成本、延迟或剩余额度选择模型；在供应商失败或限额后自动回退；组合多种压缩引擎缩减工具输出；通过 MCP、A2A 或远程 CLI 管理网关

### 05｜alibaba/open-code-review

- 仓库：https://github.com/alibaba/open-code-review
- 定位：读取代码差异并结合仓库上下文生成精确到行的审查意见，也能扫描没有有效差异的完整文件
- Star：17,572
- Fork：1,193
- 本期信号：+4,592 Star（snapshot）
- 许可证：Apache-2.0
- 能力：审查暂存、未暂存和未跟踪的改动；比较分支或指定提交并生成评论；扫描整个仓库、目录或单个文件；按文件特征匹配对应审查规则；保存审查会话并恢复中断的任务

### 06｜citrolabs/ego-lite

- 仓库：https://github.com/citrolabs/ego-lite
- 定位：让外部 AI 代理在独立浏览空间里复用你的登录状态执行网页任务，同时不占用正在操作的标签页
- Star：7,437
- Fork：371
- 本期信号：+3,829 Star（snapshot）
- 许可证：MIT
- 能力：读取页面快照并定位可交互内容；填写表单、点击元素并等待页面变化；并行运行多个互不抢占标签页的任务；调用截图、导航和页面内脚本工具；随时接管或停止代理所在的浏览空间

### 07｜1jehuang/jcode

- 仓库：https://github.com/1jehuang/jcode
- 定位：在终端里运行可记忆、可并行协作的编码代理，并统一接入多种模型、MCP 工具与浏览器操作
- Star：14,998
- Fork：1,664
- 本期信号：+3,506 Star（snapshot）
- 许可证：MIT
- 能力：启动交互式终端或单次无交互任务；搜索并注入与当前对话相关的记忆；生成代理团队并行处理同一仓库任务；切换 OAuth、API 或本地模型供应商；通过 Firefox 执行点击、填写和截图

## 配图顺序

01. `images/01-cover.png` — 封面
02. `images/02-rank-01-block-buzz.png` — block/buzz
03. `images/03-rank-02-permissionlesstech-bitchat.png` — permissionlesstech/bitchat
04. `images/04-rank-03-mattpocock-skills.png` — mattpocock/skills
05. `images/05-rank-04-diegosouzapw-omniroute.png` — diegosouzapw/OmniRoute
06. `images/06-rank-05-alibaba-open-code-review.png` — alibaba/open-code-review
07. `images/07-rank-06-citrolabs-ego-lite.png` — citrolabs/ego-lite
08. `images/08-rank-07-1jehuang-jcode.png` — 1jehuang/jcode

## 人工确认

- [ ] 标题和正文已复核
- [ ] 项目事实已复核
- [ ] 图片顺序已复核
- [ ] 发布后填写平台链接
