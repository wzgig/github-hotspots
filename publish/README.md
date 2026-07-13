# 发布工作台与历史

这个目录集中管理小红书标题、正文、审核稿和配图。流程仍止于内容生成与人工审核，不会自动登录、发布或操作小红书账号。

## 三层目录

```text
publish/
├─ current/                         # 本机最新完整图片工作台，Git 忽略
│  ├─ TODAY.md
│  ├─ daily/{01-comprehensive,02-ai}/
│  └─ weekly/{01-comprehensive,02-ai}/
├─ archive/                         # 本机旧包与人工修改备份，Git 忽略
├─ history/                         # Git 跟踪的永久薄历史
│  ├─ INDEX.json
│  ├─ INDEX.md
│  └─ <period>/<year>/<report-stem>/<revision>/
└─ logs/                            # 本地打包日志，Git 忽略
```

- `current`：每个周期只保留最新一期，包含可直接上传的有序 PNG。
- `archive`：当 `current` 内容变化时保存被替换的本地工作包，避免人工修改被静默覆盖。
- `history`：保存每期 `MANIFEST.json`、`CHECKLIST.md`、`TITLE.txt`、`CAPTION.txt` 与 `REVIEW.md`；不重复提交 PNG，而是通过路径、SHA-256 和尺寸引用 `reports/.../assets/`。

每个 `current` 榜单目录包含：

- `TITLE.txt`：复制到小红书标题栏；
- `CAPTION.txt`：复制到正文，不含内部路径和审核说明；
- `REVIEW.md`：发布前核对项目事实、许可证、图片顺序和编辑后端；
- `images/`：按 `01-cover.png`、`02-rank-01-*.png` 的数字前缀依次上传。

`current` 中的图片始终是独立副本，Manifest 的 `materialization` 固定为 `copy`。这样在发布工作台中裁剪、压缩或标注图片时，不会同时改坏 `reports` 中的版本化源图、Pages 资源或 history 哈希。

## 手动生成

正常生成会同时刷新最新工作台和永久历史：

```powershell
.\.venv\Scripts\python.exe -m github_hotspots.cli publish reports/daily/2026-07-13.json
.\.venv\Scripts\python.exe -m github_hotspots.cli publish reports/weekly/2026-W28.json
```

只回填历史、不改变较新的 `current`：

```powershell
.\.venv\Scripts\python.exe -m github_hotspots.cli publish `
  reports/daily/2026-07-12.json --history-only
```

重建索引：

```powershell
.\.venv\Scripts\python.exe -m github_hotspots.cli publish-history-index
```

旧日期默认不能覆盖较新的工作台。只有明确需要重新审核旧期时才使用 `--activate-older`。相同内容指纹重复执行不会新增 archive 或 history 修订；同一期内容发生变化时，才会生成新的指纹修订。

`history` 保存的是自动生成基线。发布前在 `current` 中进行的人工改稿不会自动写回 Git；最终发布版本和平台链接仍需由运营者另行记录。历史图片引用的是当前分支中同日期的报告资产；同日重渲染后的旧图片字节仍可通过对应 Git 提交找回，但目前没有在 history Manifest 中单独记录该提交号。
