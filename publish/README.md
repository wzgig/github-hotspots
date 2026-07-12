# 本地发布工作台

这个目录把每期小红书标题、可直接粘贴的正文、审核稿和按顺序编号的 PNG 集中到一起。生成内容仅供本机人工审核与发布，不会提交到 Git 历史，也不会自动登录或操作小红书账号。

## 当前目录

```text
publish/
├─ current/
│  ├─ TODAY.md
│  ├─ daily/
│  │  ├─ CHECKLIST.md
│  │  ├─ MANIFEST.json
│  │  ├─ 01-comprehensive/
│  │  └─ 02-ai/
│  └─ weekly/
├─ archive/
└─ logs/
```

每个榜单目录包含：

- `TITLE.txt`：直接复制到小红书标题栏；
- `CAPTION.txt`：直接复制到正文，不含内部路径和审核说明；
- `REVIEW.md`：发布前核对项目事实、许可证、图片顺序和编辑后端；
- `images/`：按 `01-cover.png`、`02-rank-01-*.png` 的文件名前缀依次上传。

`current/`、`archive/` 与 `logs/` 已被 `.gitignore` 排除。图片在同一 NTFS 卷内优先使用硬链接；跨磁盘同步或文件系统不支持时会安全复制。每张图片的实际方式记录在 `MANIFEST.json` 的 `materialization` 字段中，打开和上传时都与普通 PNG 相同。

## 手动生成

```powershell
.\.venv\Scripts\python.exe -m github_hotspots.cli publish reports/daily/2026-07-12.json
.\.venv\Scripts\python.exe -m github_hotspots.cli publish reports/weekly/2026-W28.json
```

同一期重新生成时，旧的 `current/<period>` 会先移动到 `archive/`，避免覆盖已经人工修改的文案。
