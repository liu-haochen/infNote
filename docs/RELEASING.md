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

手动选择分支运行时只构建；推送 `v*` 标签时会在所有测试通过后自动创建并发布 Release，附带 ZIP 和校验文件。标签必须与 `frontend/package.json` 的版本号一致。

## 自动发布 Release

更新 `frontend/package.json` 和 `frontend/package-lock.json` 的版本号，并在 `CHANGELOG.md` 增加对应版本的说明。将代码提交并推送后，创建匹配的标签，例如当前版本：

```powershell
git tag -a v0.1.0 -m "infNote v0.1.0"
git push origin v0.1.0
```

如果标签已存在，请检查其对应提交，不要直接覆盖已发布标签。后续修复使用新版本号。

之后无需手动上传：Actions 自动测试、打包、检查 EXE，成功后从 `CHANGELOG.md` 提取该版本的说明，上传 ZIP 和校验文件，并公开发布 Release。

发布任务使用 GitHub 提供的 `GITHUB_TOKEN`，仅该任务具有 `contents: write`，无需另配个人令牌。带连字符的版本号（如 `0.2.0-beta.1`）会标记为预发布。

附件上传完成后才公开发布；失败留下的草稿可以通过重跑恢复。已公开的同名 Release 保持不变，不覆盖既有附件。旧标签仍指向旧提交，重跑旧任务不会使用新的工作流；请发布包含新工作流的新版本标签。

若希望上传本地生成的压缩包，也可在仓库 **Releases → Draft a new release** 中选择对应标签并手动添加附件。

用户应下载你上传的 `infNote-v0.1.0-windows-x64.zip`，而不是 GitHub 自动提供的 `Source code` 压缩包。

## 更新与笔记

此便携包只包含程序，不包含你的笔记。默认笔记位置为 `%USERPROFILE%\infNoteData`。
升级时关闭旧程序、解压新版本并启动即可。发布前不要将个人数据目录放进附件。
