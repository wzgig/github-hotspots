# W003-A · AI 专题榜 发布审核

- 状态：`draft`
- 编辑后端：`codex-cli`
- 回退：`false`

## 标题

GitHub AI周报第3期｜7个AI项目值得收藏

## 可粘贴正文

2026-07-26 · AI 专题榜 · 第3期

GitHub Hotspots AI 周报第3期。去掉术语包装，用 7 张项目卡讲清实际能力、适用人群和上手前提。

先看结论：
01｜bojieli/ai-agent-book：从原理到工程实践系统学习 AI Agent，并用配套实验亲手实现关键机制
02｜stablyai/orca：把多个编程 Agent 放进隔离工作区并行执行，在一处比较结果、审查改动和继续追问
03｜tirth8205/code-review-graph：把代码库解析成持续更新的结构图，让 AI 审查改动时只读取相关文件和依赖链
04｜koala73/worldmonitor：把全球新闻、地缘事件、市场与基础设施信号汇入地图和看板，便于集中研判态势
05｜diegosouzapw/OmniRoute：用一个兼容接口连接多家模型服务，并按配额、成本、延迟或任务类型自动切换路线
06｜rohitg00/ai-engineering-from-scratch：沿着数学、模型、LLM 和 Agent 的课程路径手写实现，并把每课成果沉淀成可复用工具
07｜earendil-works/pi：用同一套组件搭建可扩展的编码 Agent，包括模型接入、工具循环、状态管理和终端界面

下周想看我深挖哪一个的真实使用门槛？

AI 辅助整理｜人工发布

#GitHub #开源项目 #AI #AI工具

## 项目事实

### 01｜bojieli/ai-agent-book

- 仓库：https://github.com/bojieli/ai-agent-book
- 定位：从原理到工程实践系统学习 AI Agent，并用配套实验亲手实现关键机制
- Star：19,975
- Fork：1,990
- 本期信号：+16,579 Star（trending）
- 许可证：Apache-2.0
- 能力：阅读从基础到工程实践的章节正文；运行各章配套项目验证关键概念；学习记忆、知识库与 RAG 的实现；练习 Coding Agent、评估与后训练；探索多模态交互和多 Agent 协作

### 02｜stablyai/orca

- 仓库：https://github.com/stablyai/orca
- 定位：把多个编程 Agent 放进隔离工作区并行执行，在一处比较结果、审查改动和继续追问
- Star：29,144
- Fork：2,068
- 本期信号：+7,330 Star（snapshot）
- 许可证：MIT
- 能力：并行启动多个编程 Agent；比较不同 Agent 的实现结果；从任务创建独立 Git worktree；批注代码差异并回传修改意见；通过手机监控任务并继续对话

### 03｜tirth8205/code-review-graph

- 仓库：https://github.com/tirth8205/code-review-graph
- 定位：把代码库解析成持续更新的结构图，让 AI 审查改动时只读取相关文件和依赖链
- Star：26,441
- Fork：2,471
- 本期信号：+6,296 Star（snapshot）
- 许可证：MIT
- 能力：构建函数、类、导入和调用关系图；定位代码改动的影响范围；增量更新发生变化的文件；生成风险分级的合并请求审查；导出架构图、Wiki 和图数据

### 04｜koala73/worldmonitor

- 仓库：https://github.com/koala73/worldmonitor
- 定位：把全球新闻、地缘事件、市场与基础设施信号汇入地图和看板，便于集中研判态势
- Star：74,270
- Fork：11,151
- 本期信号：+12,085 Star（trending）
- 许可证：AGPL-3.0-only
- 能力：汇总多类别新闻源并生成简报；切换地球和平面地图查看事件；关联不同数据流中的共同信号；追踪市场、能源、航空和基础设施；通过 MCP、REST、CLI 或 SDK 查询

### 05｜diegosouzapw/OmniRoute

- 仓库：https://github.com/diegosouzapw/OmniRoute
- 定位：用一个兼容接口连接多家模型服务，并按配额、成本、延迟或任务类型自动切换路线
- Star：30,198
- Fork：3,935
- 本期信号：+11,147 Star（trending）
- 许可证：MIT
- 能力：接入不同供应商和模型账户；按配额、成本或延迟选择模型；在供应商失败时切换后备路线；为编程 CLI 写入网关配置；压缩提示和工具输出以缩短上下文

### 06｜rohitg00/ai-engineering-from-scratch

- 仓库：https://github.com/rohitg00/ai-engineering-from-scratch
- 定位：沿着数学、模型、LLM 和 Agent 的课程路径手写实现，并把每课成果沉淀成可复用工具
- Star：43,526
- Fork：7,292
- 本期信号：+4,441 Star（snapshot）
- 许可证：MIT
- 能力：从数学推导并实现机器学习算法；手写注意力、Transformer 和小型模型；构建 RAG、工具调用与 MCP 服务；练习 Agent 循环、记忆和多 Agent 协作；完成端到端 AI 工程综合项目

### 07｜earendil-works/pi

- 仓库：https://github.com/earendil-works/pi
- 定位：用同一套组件搭建可扩展的编码 Agent，包括模型接入、工具循环、状态管理和终端界面
- Star：77,656
- Fork：9,560
- 本期信号：+5,167 Star（trending）
- 许可证：MIT
- 能力：统一调用不同模型供应商；运行带工具调用的 Agent 循环；保存和更新 Agent 状态；构建差分渲染的终端界面；使用交互式编码 Agent CLI

## 配图顺序

01. `images/01-cover.png` — 封面
02. `images/02-rank-01-bojieli-ai-agent-book.png` — bojieli/ai-agent-book
03. `images/03-rank-02-stablyai-orca.png` — stablyai/orca
04. `images/04-rank-03-tirth8205-code-review-graph.png` — tirth8205/code-review-graph
05. `images/05-rank-04-koala73-worldmonitor.png` — koala73/worldmonitor
06. `images/06-rank-05-diegosouzapw-omniroute.png` — diegosouzapw/OmniRoute
07. `images/07-rank-06-rohitg00-ai-engineering-from-scratch.png` — rohitg00/ai-engineering-from-scratch
08. `images/08-rank-07-earendil-works-pi.png` — earendil-works/pi

## 人工确认

- [ ] 标题和正文已复核
- [ ] 项目事实已复核
- [ ] 图片顺序已复核
- [ ] 发布后填写平台链接
