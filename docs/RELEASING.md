# 发布 Windows 便携版

目标产物：`infNote-v0.1.0-windows-x64.zip`。用户完整解压后双击 `infNote.exe`，无需安装 Python 或 Node.js。
界面仍在浏览器中打开，本地服务通过 EXE 启动。此版本保留控制台窗口，用于停止服务和查看错误。

## 方法一：本机打包

在 Windows x64 上安装 Python 3.10+ 与 Node.js。在项目根目录运行：

```powershell
python scripts/build_release.py
python scripts/smoke_portable.py
```

脚本会构建页面，创建独立的 `.venv-build` 打包环境，使用 PyInstaller 将运行环境、本地后台和前端页面打包。
首次打包需要联网下载依赖。版本号读取自 `frontend/package.json`。

产物在 `release/output/`：

- `infNote-v0.1.0-windows-x64.zip`
- `infNote-v0.1.0-windows-x64.sha256`

冒烟测试会运行生成的 EXE，使用隔离的临时笔记目录和端口，验证页面、静态资源、保存和重启恢复。测试时 PATH 不包含 Python / Node.js。
建议正式公开前，再在没有开发环境的 Windows 电脑上进行一次手动粘贴与编辑验证。

## 方法二：GitHub Actions 打包

将打包脚本及 `.github/workflows/windows-build.yml` 提交并推送到 GitHub 后：

1. 打开仓库 **Actions → Build Windows portable → Run workflow**，选择需要构建的分支。
2. 等待构建、自动测试和 EXE 冒烟测试通过。
3. 在该次运行的 **Artifacts** 下载 `infNote-windows-x64`。
4. 解开下载的 artifact 压缩包，取出里面的便携版 ZIP 和 `.sha256` 文件。

推送 `v*` 标签也会触发构建；标签必须与 `frontend/package.json` 的版本号一致。工作流只生成构建产物，不会自动公开发布 Release。

## 在 GitHub 创建 Release

先确保发布对应的代码已经提交并推送，然后创建标签：

```powershell
git tag -a v0.1.0 -m "infNote v0.1.0"
git push origin v0.1.0
```

如果标签已存在，请检查其对应提交，不要直接覆盖已发布标签。后续修复使用新版本号。

1. 打开仓库 **Releases → Draft a new release**。
2. 选择标签 `v0.1.0`，标题填写 `infNote v0.1.0`。
3. 发布说明复制 `CHANGELOG.md` 中该版本的内容，并注明“Windows x64，完整解压后运行 infNote.exe，无需 Python / Node.js”。
4. 将便携版 ZIP 和 `.sha256` 文件作为附件上传。
5. 检查无误后点击 **Publish release**。

用户应下载你上传的 `infNote-v0.1.0-windows-x64.zip`，而不是 GitHub 自动提供的 `Source code` 压缩包。

## 更新与笔记

此便携包只包含程序，不包含你的笔记。默认笔记位置为 `%USERPROFILE%\infNoteData`。
升级时关闭旧程序、解压新版本并启动即可。发布前不要将个人数据目录放进附件。
