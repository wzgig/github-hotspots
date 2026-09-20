# W011-A · AI 专题榜 发布审核

- 状态：`draft`
- 编辑后端：`codex-cli`
- 回退：`false`

## 标题

GitHub AI周报第11期｜7个AI项目值得收藏

## 可粘贴正文

2026-09-20 · AI 专题榜 · 第11期

GitHub Hotspots AI 周报第11期。去掉术语包装，用 7 张项目卡讲清实际能力、适用人群和上手前提。

先看结论：
01｜deepseek-ai/deepseek-harness：为开发者提供以插件扩展的智能体运行框架，并配有可在本机启动的网页界面。
02｜affaan-m/ECC：把反复提醒 AI 的计划、测试、审查和记忆步骤，变成可安装的研发工作流。
03｜alibaba/open-code-review：在代码合并前读取变更和相关文件，为团队生成定位到代码行的审查意见。
04｜Tencent/WeKnora：把散落的文档变成团队可提问、可追溯来源，也能持续编辑的知识库和 Wiki。
05｜DietrichGebert/ponytail：给编程 AI 加一套“先复用、再新增”的规则，帮开发者少写不必要的代码。
06｜stablyai/orca：让多个编程 AI 在各自工作目录里并行做题，开发者集中比较结果、批注改动并选择合并。
07｜obra/superpowers：从一句开发想法开始，带着编程 AI 走完需求确认、计划、测试、实现与审查，而不是直接堆代码。

下周想看我深挖哪一个的真实使用门槛？

AI 辅助整理｜人工发布

#GitHub #开源项目 #AI #AI工具

## 项目事实

### 01｜deepseek-ai/deepseek-harness

- 仓库：https://github.com/deepseek-ai/deepseek-harness
- 定位：为开发者提供以插件扩展的智能体运行框架，并配有可在本机启动的网页界面。
- Star：230,029
- Fork：27,542
- 本期信号：+8,130 Star（snapshot）
- 许可证：MIT
- 能力：通过插件扩展智能体运行框架；在本机启动浏览器操作界面；以不打开浏览器的方式启动服务

### 02｜affaan-m/ECC

- 仓库：https://github.com/affaan-m/ECC
- 定位：把反复提醒 AI 的计划、测试、审查和记忆步骤，变成可安装的研发工作流。
- Star：262,955
- Fork：39,344
- 本期信号：+5,676 Star（snapshot）
- 许可证：MIT
- 能力：把功能需求整理成实施计划；按先写失败测试的流程实现功能；用独立上下文审查代码变更；保存可跨编程工具检索的会话记忆；扫描智能体配置中的权限与注入风险

### 03｜alibaba/open-code-review

- 仓库：https://github.com/alibaba/open-code-review
- 定位：在代码合并前读取变更和相关文件，为团队生成定位到代码行的审查意见。
- Star：37,551
- Fork：2,684
- 本期信号：+15,028 Star（trending）
- 许可证：Apache-2.0
- 能力：审查工作区、分支或单次提交的变更；扫描没有有效差异记录的完整文件；检索代码库以补充审查上下文；导出带代码行位置的结构化意见；恢复被中断的审查或全文件扫描

### 04｜Tencent/WeKnora

- 仓库：https://github.com/Tencent/WeKnora
- 定位：把散落的文档变成团队可提问、可追溯来源，也能持续编辑的知识库和 Wiki。
- Star：27,426
- Fork：3,693
- 本期信号：+4,699 Star（snapshot）
- 许可证：MIT License
- 能力：同步飞书、Notion 等来源的文档；从知识库检索资料并生成带引用的回答；把原始文档整理成互相链接的 Wiki；编辑检索片段并回退历史版本；调度检索、外部工具和沙箱处理多步任务

### 05｜DietrichGebert/ponytail

- 仓库：https://github.com/DietrichGebert/ponytail
- 定位：给编程 AI 加一套“先复用、再新增”的规则，帮开发者少写不必要的代码。
- Star：142,524
- Fork：7,648
- 本期信号：+5,699 Star（snapshot）
- 许可证：MIT
- 能力：引导智能体优先复用已有代码与原生能力；检查当前变更并列出可删除的冗余实现；审计整个仓库中的过度设计；把暂缓处理的简化项汇总成台账；切换规则强度或关闭规则

### 06｜stablyai/orca

- 仓库：https://github.com/stablyai/orca
- 定位：让多个编程 AI 在各自工作目录里并行做题，开发者集中比较结果、批注改动并选择合并。
- Star：72,617
- Fork：4,752
- 本期信号：+5,404 Star（trending）
- 许可证：MIT
- 能力：把同一提示分发给独立工作区中的智能体；将界面元素的代码与截图送入提示；给差异行添加反馈并发回智能体；通过 SSH 在远程机器运行编程任务；在手机接收完成通知并追加指令

### 07｜obra/superpowers

- 仓库：https://github.com/obra/superpowers
- 定位：从一句开发想法开始，带着编程 AI 走完需求确认、计划、测试、实现与审查，而不是直接堆代码。
- Star：288,832
- Fork：25,838
- 本期信号：+2,931 Star（snapshot）
- 许可证：MIT
- 能力：通过提问把模糊想法整理成设计文档；将批准的设计拆成含验证步骤的小任务；创建隔离分支工作区并检查测试基线；按失败测试到通过测试的顺序实现功能；派发子任务并审查需求符合度与代码质量

## 配图顺序

01. `images/01-cover.png` — 封面
02. `images/02-rank-01-deepseek-ai-deepseek-harness.png` — deepseek-ai/deepseek-harness
03. `images/03-rank-02-affaan-m-ecc.png` — affaan-m/ECC
04. `images/04-rank-03-alibaba-open-code-review.png` — alibaba/open-code-review
05. `images/05-rank-04-tencent-weknora.png` — Tencent/WeKnora
06. `images/06-rank-05-dietrichgebert-ponytail.png` — DietrichGebert/ponytail
07. `images/07-rank-06-stablyai-orca.png` — stablyai/orca
08. `images/08-rank-07-obra-superpowers.png` — obra/superpowers

## 人工确认

- [ ] 标题和正文已复核
- [ ] 项目事实已复核
- [ ] 图片顺序已复核
- [ ] 发布后填写平台链接
