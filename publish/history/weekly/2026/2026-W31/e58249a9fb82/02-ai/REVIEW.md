# W004-A · AI 专题榜 发布审核

- 状态：`draft`
- 编辑后端：`codex-cli`
- 回退：`false`

## 标题

GitHub AI周报第4期｜7个AI项目值得收藏

## 可粘贴正文

2026-08-02 · AI 专题榜 · 第4期

GitHub Hotspots AI 周报第4期。去掉术语包装，用 7 张项目卡讲清实际能力、适用人群和上手前提。

先看结论：
01｜diegosouzapw/OmniRoute：把不同模型供应商收进一个本地网关，按配额、成本或延迟自动选路并故障切换。
02｜alibaba/open-code-review：读取 Git 变更后，用确定性流程锁定审查范围，再让 Agent 给出精确到行的结构化意见。
03｜citrolabs/ego-lite：让 AI Agent 继承你的浏览器登录状态，在独立空间并行跑网页任务，同时不占用你的标签页。
04｜1jehuang/jcode：在终端里运行可记忆、可并行协作的编程 Agent，并用常驻服务承载多个低资源会话。
05｜obra/superpowers：把需求澄清、设计确认、测试先行、分工实现和代码复核装进编程 Agent 的固定工作流。
06｜NousResearch/hermes-agent：把长期记忆、自动学技能、多渠道消息和定时任务放进同一个可远程运行的个人 Agent。
07｜affaan-m/ECC：给不同编程 Agent 补上一套可复用工程体系，让计划、测试、复核、记忆和安全检查连续运转。

下周想看我深挖哪一个的真实使用门槛？

AI 辅助整理｜人工发布

#GitHub #开源项目 #AI #AI工具

## 项目事实

### 01｜diegosouzapw/OmniRoute

- 仓库：https://github.com/diegosouzapw/OmniRoute
- 定位：把不同模型供应商收进一个本地网关，按配额、成本或延迟自动选路并故障切换。
- Star：37,213
- Fork：4,820
- 本期信号：+7,015 Star（snapshot）
- 许可证：MIT
- 能力：接入不同供应商的聊天、图像与音频接口；按配额、成本、延迟或成功率自动选路；把多个模型串成前后衔接的处理流水线；压缩提示与工具输出以减少上下文占用；通过 MCP、A2A 或远程 CLI 交给 Agent 控制

### 02｜alibaba/open-code-review

- 仓库：https://github.com/alibaba/open-code-review
- 定位：读取 Git 变更后，用确定性流程锁定审查范围，再让 Agent 给出精确到行的结构化意见。
- Star：17,572
- Fork：1,193
- 本期信号：+4,592 Star（snapshot）
- 许可证：Apache-2.0
- 能力：读取暂存、未暂存和未跟踪的代码变更；比较分支、提交或指定范围的差异；搜索完整文件和仓库上下文核对问题；生成精确到代码行的结构化审查意见；扫描整份文件或目录而不依赖差异

### 03｜citrolabs/ego-lite

- 仓库：https://github.com/citrolabs/ego-lite
- 定位：让 AI Agent 继承你的浏览器登录状态，在独立空间并行跑网页任务，同时不占用你的标签页。
- Star：7,437
- Fork：371
- 本期信号：+3,829 Star（snapshot）
- 许可证：MIT
- 能力：迁移 Chrome 登录、Cookie、扩展和书签；为每个 Agent 创建隔离的浏览空间；并行运行多个互不抢标签页的网页任务；读取页面快照并执行点击、填写和导航；通过 JavaScript 工具组合多步浏览流程

### 04｜1jehuang/jcode

- 仓库：https://github.com/1jehuang/jcode
- 定位：在终端里运行可记忆、可并行协作的编程 Agent，并用常驻服务承载多个低资源会话。
- Star：14,998
- Fork：1,664
- 本期信号：+3,506 Star（snapshot）
- 许可证：MIT
- 能力：在 TUI 或非交互模式执行编程任务；自动检索会话记忆并注入相关上下文；启动多个 Agent 协作并提醒文件冲突；连接多家模型或自托管兼容端点；控制 Firefox 完成页面点击、输入和截图

### 05｜obra/superpowers

- 仓库：https://github.com/obra/superpowers
- 定位：把需求澄清、设计确认、测试先行、分工实现和代码复核装进编程 Agent 的固定工作流。
- Star：264,852
- Fork：23,648
- 本期信号：+3,650 Star（snapshot）
- 许可证：MIT
- 能力：通过提问把模糊想法整理成可确认设计；把设计拆成带文件路径和验证步骤的计划；按测试先行循环实现最小改动；为每个任务派出独立子 Agent 执行；在合并前复核规格、代码质量和测试结果

### 06｜NousResearch/hermes-agent

- 仓库：https://github.com/NousResearch/hermes-agent
- 定位：把长期记忆、自动学技能、多渠道消息和定时任务放进同一个可远程运行的个人 Agent。
- Star：223,923
- Fork：43,237
- 本期信号：+3,359 Star（snapshot）
- 许可证：MIT
- 能力：从历史对话提取记忆并跨会话召回；把复杂任务经验整理成可复用技能；通过聊天平台与终端延续同一段对话；按自然语言计划定时报告、备份或审计；派出隔离子 Agent 并行处理不同工作流

### 07｜affaan-m/ECC

- 仓库：https://github.com/affaan-m/ECC
- 定位：给不同编程 Agent 补上一套可复用工程体系，让计划、测试、复核、记忆和安全检查连续运转。
- Star：236,864
- Fork：36,014
- 本期信号：+3,467 Star（snapshot）
- 许可证：MIT
- 能力：按需加载规划、测试、安全和文档技能；派出专门 Agent 处理评审、构建和架构；用 hooks 在模型上下文外执行确定性检查；把会话摘要和经验保存为可检索记忆；扫描提示、权限、MCP、密钥和 Agent 配置

## 配图顺序

01. `images/01-cover.png` — 封面
02. `images/02-rank-01-diegosouzapw-omniroute.png` — diegosouzapw/OmniRoute
03. `images/03-rank-02-alibaba-open-code-review.png` — alibaba/open-code-review
04. `images/04-rank-03-citrolabs-ego-lite.png` — citrolabs/ego-lite
05. `images/05-rank-04-1jehuang-jcode.png` — 1jehuang/jcode
06. `images/06-rank-05-obra-superpowers.png` — obra/superpowers
07. `images/07-rank-06-nousresearch-hermes-agent.png` — NousResearch/hermes-agent
08. `images/08-rank-07-affaan-m-ecc.png` — affaan-m/ECC

## 人工确认

- [ ] 标题和正文已复核
- [ ] 项目事实已复核
- [ ] 图片顺序已复核
- [ ] 发布后填写平台链接
