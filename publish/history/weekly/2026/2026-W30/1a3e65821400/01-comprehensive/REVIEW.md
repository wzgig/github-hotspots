# W003-C · 综合主榜 发布审核

- 状态：`draft`
- 编辑后端：`codex-cli`
- 回退：`false`

## 标题

GitHub周报第3期｜7个开源项目值得收藏

## 可粘贴正文

2026-07-26 · 综合主榜 · 第3期

GitHub Hotspots 周报第3期。把这一周的 7 个热点压缩成一组可收藏的项目卡：先看用途，再看为什么值得关注。

先看结论：
01｜mattpocock/skills：把软件工程方法拆成可组合的 Agent 技能，帮助编码助手先对齐需求，再测试、调试与审查改动
02｜tirth8205/code-review-graph：把代码库解析成持久结构图，让 AI 审查改动时只读取相关函数、依赖文件和测试
03｜stablyai/orca：在隔离的 Git worktree 中并行运行多个编程 Agent，并从桌面或手机统一跟进结果
04｜bojieli/ai-agent-book：从 LLM、上下文和工具的组合原理出发，用章节正文与配套实验讲清 AI Agent 的工程实现
05｜rohitg00/ai-engineering-from-scratch：从数学基础一路学到 Agent、部署与安全，每课都要求亲手实现并留下可复用工具
06｜koala73/worldmonitor：把全球新闻、地缘信号、金融与基础设施数据汇入同一套地图和态势仪表盘
07｜diegosouzapw/OmniRoute：给编码工具提供统一模型端点，并按配额、成本、延迟和故障情况自动切换供应商

这一周你最想把哪一个加入收藏夹？

AI 辅助整理｜人工发布

#GitHub #开源项目 #程序员 #开发者工具

## 项目事实

### 01｜mattpocock/skills

- 仓库：https://github.com/mattpocock/skills
- 定位：把软件工程方法拆成可组合的 Agent 技能，帮助编码助手先对齐需求，再测试、调试与审查改动
- Star：188,544
- Fork：16,197
- 本期信号：+11,961 Star（snapshot）
- 许可证：MIT
- 能力：追问需求并补齐决策分支；建立项目术语表与架构决策记录；把对话整理成规格和可阻塞工单；按测试驱动循环实现功能或修复缺陷；审查改动是否符合规范与原始规格

### 02｜tirth8205/code-review-graph

- 仓库：https://github.com/tirth8205/code-review-graph
- 定位：把代码库解析成持久结构图，让 AI 审查改动时只读取相关函数、依赖文件和测试
- Star：26,441
- Fork：2,471
- 本期信号：+6,296 Star（snapshot）
- 许可证：MIT
- 能力：解析代码并建立函数、类和导入关系图；增量更新发生变化的文件；追踪改动涉及的调用方、依赖和测试；在合并请求中发布风险审查评论；导出交互图、GraphML 或代码库 Wiki

### 03｜stablyai/orca

- 仓库：https://github.com/stablyai/orca
- 定位：在隔离的 Git worktree 中并行运行多个编程 Agent，并从桌面或手机统一跟进结果
- Star：29,144
- Fork：2,068
- 本期信号：+7,330 Star（snapshot）
- 许可证：MIT
- 能力：并排运行任意终端型编程 Agent；把同一提示分发到多个隔离 worktree；批注差异行并把意见发回 Agent；从手机监控任务并发送后续要求；通过 SSH 在远程主机运行 Agent

### 04｜bojieli/ai-agent-book

- 仓库：https://github.com/bojieli/ai-agent-book
- 定位：从 LLM、上下文和工具的组合原理出发，用章节正文与配套实验讲清 AI Agent 的工程实现
- Star：19,975
- Fork：1,990
- 本期信号：+16,579 Star（trending）
- 许可证：Apache-2.0
- 能力：阅读从基础到多 Agent 协作的章节；运行按章配套的代码实验；下载 PDF 或 EPUB 离线阅读；按脚本编译多语言电子书；克隆外部仓库补齐进阶实验

### 05｜rohitg00/ai-engineering-from-scratch

- 仓库：https://github.com/rohitg00/ai-engineering-from-scratch
- 定位：从数学基础一路学到 Agent、部署与安全，每课都要求亲手实现并留下可复用工具
- Star：43,526
- Fork：7,292
- 本期信号：+4,441 Star（snapshot）
- 许可证：MIT
- 能力：推导并编码机器学习与深度学习算法；从零实现注意力、模型和 Agent 循环；运行测试并比较手写实现与常用框架；按知识水平生成个性化学习路径；安装课程产出的提示词与 Agent 技能

### 06｜koala73/worldmonitor

- 仓库：https://github.com/koala73/worldmonitor
- 定位：把全球新闻、地缘信号、金融与基础设施数据汇入同一套地图和态势仪表盘
- Star：74,270
- Fork：11,151
- 本期信号：+12,085 Star（trending）
- 许可证：AGPL-3.0-only
- 能力：汇总新闻源并生成 AI 简报；切换三维地球与 WebGL 平面地图；关联跨数据流的异常与升级信号；查看交易所、商品和加密资产雷达；通过 MCP、REST、CLI 或 SDK 查询数据

### 07｜diegosouzapw/OmniRoute

- 仓库：https://github.com/diegosouzapw/OmniRoute
- 定位：给编码工具提供统一模型端点，并按配额、成本、延迟和故障情况自动切换供应商
- Star：30,198
- Fork：3,935
- 本期信号：+11,147 Star（trending）
- 许可证：MIT
- 能力：把不同供应商接到统一兼容端点；按配额、成本或延迟自动选择模型；在供应商失败时切换到后备目标；压缩提示词、工具输出和历史上下文；通过 MCP、A2A 和远程 CLI 管理网关

## 配图顺序

01. `images/01-cover.png` — 封面
02. `images/02-rank-01-mattpocock-skills.png` — mattpocock/skills
03. `images/03-rank-02-tirth8205-code-review-graph.png` — tirth8205/code-review-graph
04. `images/04-rank-03-stablyai-orca.png` — stablyai/orca
05. `images/05-rank-04-bojieli-ai-agent-book.png` — bojieli/ai-agent-book
06. `images/06-rank-05-rohitg00-ai-engineering-from-scratch.png` — rohitg00/ai-engineering-from-scratch
07. `images/07-rank-06-koala73-worldmonitor.png` — koala73/worldmonitor
08. `images/08-rank-07-diegosouzapw-omniroute.png` — diegosouzapw/OmniRoute

## 人工确认

- [ ] 标题和正文已复核
- [ ] 项目事实已复核
- [ ] 图片顺序已复核
- [ ] 发布后填写平台链接
