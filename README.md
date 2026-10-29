# infNote · 无限知识画布

React + TypeScript + React Flow / Python + FastAPI。本地运行，截图和文字自动保存在硬盘。

## 启动

便携版发布后，可下载 `infNote-v0.1.0-windows-x64.zip`，完整解压并双击 `infNote.exe`；无需安装 Python / Node.js。保留同目录的 `_internal` 文件夹。笔记仍保存在用户目录。

以下为源码启动方式：

需要 Python 3.10+、Node.js 20.19+（或 22.12+）。Windows 双击 `start.bat`，或运行 `python start.py`。
首次启动会安装缺失的 Python 依赖、安装前端依赖并构建页面，需要联网；之后正常使用无需网络。保留启动窗口，关闭窗口会停止服务。

打开 http://127.0.0.1:8765 。仅支持一个服务实例和一个编辑页面。

## 操作

- Ctrl+V：粘贴截图或文字；也可拖入图片或点击“导入图片”。
- 双击文字卡片：编辑 Markdown；点击外部或 Ctrl+Enter 完成。
- 拖动卡片移动；选中后拖动边框调整尺寸。图片保持比例。
- 空格 + 左键拖动（或中键 / 右键拖动）：平移；滚轮：缩放。
- 空白处拖动框选，Shift 多选，Delete 删除。
- Ctrl+Z 撤销，Ctrl+Shift+Z / Ctrl+Y 重做；仅保留当前画布会话最近 60 步。
- 双击截图查看大图，可以缩放或在新标签页查看原文件。
- 自动保存延迟约 500ms；保存失败点击“重试”。关闭前确认显示“所有更改已保存”。

## 数据与备份

默认目录 `%USERPROFILE%\infNoteData`，界面左下角显示并可复制。包含 `index.json`、`canvases/*.json`、`assets/*`。
设置环境变量 `INFNOTE_DATA_DIR` 可修改数据目录。关闭服务后复制整个目录即可备份，恢复时替换整个目录。
每张画布保留上一份有效 `.bak`；主文件损坏时尝试读取备份。删除卡片不会清理原图。

## 开发与扩展

后端：`python -m uvicorn backend.dev:app --host 127.0.0.1 --port 8765`

前端：在 `frontend` 中运行 `npm ci`、`npm run dev`，浏览器打开 Vite 显示的地址。正式使用由 FastAPI 直接提供构建后的页面。

后端接口见 `/docs`。前端存储接口位于 `frontend/src/storage.ts`。
内部扩展入口 `window.infNote` 提供 `getSelectedCards()`、`getOriginalImage(card)`、`createCards(cards)`，仅用于后续开发，尚无第三方插件安装器。
卡片使用稳定 ID，OCR / AI 可通过创建新卡片保留原始内容。

测试：`python -m unittest discover -s tests -v`；前端检查与构建：`cd frontend` 后 `npm run build`。

MVP 暂无连线、分组、搜索、OCR、AI、云同步和多标签页并发编辑。请勿同时在多个页面编辑同一数据目录。

## 版本发布

当前版本为 `0.1.0`，更新说明见 [CHANGELOG.md](CHANGELOG.md)。

推送到自己的空仓库：

```powershell
git remote add origin <你的仓库地址>
git push -u origin main
```

准备发布时，为确认过的提交创建版本标签并推送：

```powershell
git tag -a v0.1.0 -m "infNote v0.1.0"
git push origin v0.1.0
```

然后在仓库托管平台创建 Release，选择 `v0.1.0` 标签，使用更新记录作为发布说明。
生成可直接使用的 Windows 压缩包和发布的完整步骤见 [发布指南](docs/RELEASING.md)。GitHub 自动提供的 `Source code (zip)` 仅包含源码，不是便携版。
