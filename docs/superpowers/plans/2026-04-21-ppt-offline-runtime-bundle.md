# PPT Offline Runtime Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在项目根目录生成一个可直接压缩带入公司内网的 `ppt_offline_runtime/` 离线运行时目录，包含 PowerPoint 本地解析所需 wheel、静默安装脚本、校验脚本、版本记录与中文说明。

**Architecture:** 以 `ppt_offline_runtime/` 为单一打包入口，将 Python wheel、`LibreOffice` 占位目录、PowerShell 安装/校验脚本、版本记录与日志目录全部收敛进去。安装脚本负责离线安装 `markitdown[pptx]` 与相关 wheel，并自动尝试静默安装 `LibreOffice`；校验脚本负责做真实 `pptx` 解析验证。

**Tech Stack:** PowerShell, Python, pip wheel, MarkItDown, onnxruntime, LibreOffice, pytest

---

### Task 1: 创建离线运行时目录骨架与占位文件

**Files:**
- Create: `ppt_offline_runtime/README.md`
- Create: `ppt_offline_runtime/VERSION_MANIFEST.md`
- Create: `ppt_offline_runtime/libreoffice/README.md`
- Create: `ppt_offline_runtime/logs/.gitkeep`
- Create: `ppt_offline_runtime/records/dependency-lock.txt`
- Create: `ppt_offline_runtime/records/hashes.txt`
- Create: `ppt_offline_runtime/records/runtime-notes.md`

- [ ] **Step 1: 创建目录结构**

Run:

```powershell
New-Item -ItemType Directory -Force -Path `
  ppt_offline_runtime, `
  ppt_offline_runtime\\wheels, `
  ppt_offline_runtime\\libreoffice, `
  ppt_offline_runtime\\scripts, `
  ppt_offline_runtime\\records, `
  ppt_offline_runtime\\logs
```

Expected:

```text
All directories created successfully
```

- [ ] **Step 2: 创建 `logs/.gitkeep`**

Create file:

```text

```

- [ ] **Step 3: 写最小占位 README 与记录文件**

Add initial content so the directory is self-describing even before wheels are downloaded.

- [ ] **Step 4: 验证目录结构存在**

Run:

```powershell
Get-ChildItem ppt_offline_runtime -Recurse | Select-Object FullName
```

Expected:

```text
Shows wheels/, libreoffice/, scripts/, records/, logs/ and created files
```

- [ ] **Step 5: Commit**

```bash
git add ppt_offline_runtime
git commit -m "chore: scaffold ppt offline runtime bundle"
```

### Task 2: 下载并固化离线 wheel 包

**Files:**
- Modify: `ppt_offline_runtime/wheels/*`
- Modify: `ppt_offline_runtime/VERSION_MANIFEST.md`
- Modify: `ppt_offline_runtime/records/dependency-lock.txt`
- Modify: `ppt_offline_runtime/records/runtime-notes.md`

- [ ] **Step 1: 下载 `markitdown[pptx]` wheel 闭包**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip download -d ppt_offline_runtime\wheels "markitdown[pptx]==0.1.5"
```

Expected:

```text
All required wheel files downloaded into ppt_offline_runtime\wheels
```

- [ ] **Step 2: 明确补充并锁定 `onnxruntime==1.20.1`**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip download -d ppt_offline_runtime\wheels "onnxruntime==1.20.1"
```

Expected:

```text
onnxruntime-1.20.1-*.whl present in wheels directory
```

- [ ] **Step 3: 生成依赖清单**

Run:

```powershell
Get-ChildItem ppt_offline_runtime\wheels -File | Sort-Object Name | Select-Object -ExpandProperty Name | Set-Content ppt_offline_runtime\records\dependency-lock.txt
```

Expected:

```text
dependency-lock.txt contains wheel filenames
```

- [ ] **Step 4: 在 `VERSION_MANIFEST.md` 与 `runtime-notes.md` 中记录版本变化**

Must explicitly record:

```text
markitdown==0.1.5
magika==0.6.3
onnxruntime changed from 1.24.3 to 1.20.1 because of markitdown dependency closure
```

- [ ] **Step 5: Commit**

```bash
git add ppt_offline_runtime/wheels ppt_offline_runtime/VERSION_MANIFEST.md ppt_offline_runtime/records/dependency-lock.txt ppt_offline_runtime/records/runtime-notes.md
git commit -m "chore: bundle offline markitdown runtime wheels"
```

### Task 3: 生成 hash 与环境信息记录

**Files:**
- Modify: `ppt_offline_runtime/records/hashes.txt`
- Create: `ppt_offline_runtime/scripts/collect_runtime_info.ps1`

- [ ] **Step 1: 写 hash 生成脚本逻辑**

Create script skeleton:

```powershell
param(
    [string]$RuntimeRoot = (Resolve-Path "$PSScriptRoot\..").Path
)

$wheelDir = Join-Path $RuntimeRoot "wheels"
$output = Join-Path $RuntimeRoot "records\hashes.txt"

Get-ChildItem $wheelDir -File |
    Sort-Object Name |
    Get-FileHash -Algorithm SHA256 |
    ForEach-Object { "$($_.Algorithm) $($_.Hash) $([System.IO.Path]::GetFileName($_.Path))" } |
    Set-Content $output -Encoding UTF8
```

- [ ] **Step 2: 写环境信息采集脚本**

Script must capture:

```powershell
python executable
markitdown version
onnxruntime version
soffice path
PowerPoint loader import result
```

- [ ] **Step 3: 运行 hash 生成逻辑**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ppt_offline_runtime\scripts\collect_runtime_info.ps1
```

Expected:

```text
hashes.txt and a runtime info log are generated
```

- [ ] **Step 4: Commit**

```bash
git add ppt_offline_runtime/records/hashes.txt ppt_offline_runtime/scripts/collect_runtime_info.ps1
git commit -m "chore: add runtime hash and info collection scripts"
```

### Task 4: 实现一键安装脚本

**Files:**
- Create: `ppt_offline_runtime/scripts/helpers.ps1`
- Create: `ppt_offline_runtime/scripts/install_offline_runtime.ps1`
- Modify: `ppt_offline_runtime/README.md`
- Modify: `ppt_offline_runtime/libreoffice/README.md`

- [ ] **Step 1: 在 `helpers.ps1` 中实现公共函数**

Functions required:

```powershell
Write-Log
Assert-Admin
Find-LibreOfficeInstaller
Find-Soffice
Ensure-VenvPython
```

- [ ] **Step 2: 实现离线 Python 安装逻辑**

Core command:

```powershell
& $VenvPython -m pip install --no-index --find-links="$WheelDir" "markitdown[pptx]==0.1.5" "onnxruntime==1.20.1"
```

- [ ] **Step 3: 实现 LibreOffice 自动静默安装逻辑**

Behavior:

- Prefer `.msi`
- Support common `.exe`
- If no installer found, log warning and continue Python install
- If not admin, log warning and skip LibreOffice install

- [ ] **Step 4: 运行脚本做本机安装验证**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ppt_offline_runtime\scripts\install_offline_runtime.ps1
```

Expected:

```text
Python offline runtime installed
LibreOffice installation attempted or skipped with clear reason
install log generated
```

- [ ] **Step 5: Commit**

```bash
git add ppt_offline_runtime/scripts/helpers.ps1 ppt_offline_runtime/scripts/install_offline_runtime.ps1 ppt_offline_runtime/README.md ppt_offline_runtime/libreoffice/README.md
git commit -m "feat: add offline runtime install script"
```

### Task 5: 实现一键校验脚本

**Files:**
- Create: `ppt_offline_runtime/scripts/verify_offline_runtime.ps1`
- Modify: `ppt_offline_runtime/README.md`

- [ ] **Step 1: 写出真实校验脚本**

The script must:

- verify `import markitdown`
- verify `onnxruntime` version
- verify `soffice --version`
- generate a real `.pptx`
- run `MarkItDown` on that `.pptx`
- run project `PowerPointMarkdownLoader` on that `.pptx`

- [ ] **Step 2: 运行校验脚本**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ppt_offline_runtime\scripts\verify_offline_runtime.ps1
```

Expected:

```text
markitdown ok
onnxruntime version ok
PowerPoint loader import ok
real pptx parse ok
verification log generated
```

- [ ] **Step 3: Commit**

```bash
git add ppt_offline_runtime/scripts/verify_offline_runtime.ps1 ppt_offline_runtime/README.md
git commit -m "feat: add offline runtime verification script"
```

### Task 6: 完善中文 README 与最终打包说明

**Files:**
- Modify: `ppt_offline_runtime/README.md`
- Modify: `ppt_offline_runtime/VERSION_MANIFEST.md`
- Modify: `ppt_offline_runtime/records/runtime-notes.md`

- [ ] **Step 1: 完整写出中文 README**

Sections required:

```text
这个目录是干什么的
你需要准备什么
LibreOffice 安装包放哪里
如何运行 install_offline_runtime.ps1
如何运行 verify_offline_runtime.ps1
如何确认 pptx 与 ppt 可用
常见错误与排查
```

- [ ] **Step 2: 完善 `VERSION_MANIFEST.md`**

Must contain:

```text
validated runtime versions
onnxruntime downgrade note
do-not-upgrade-individually warning
```

- [ ] **Step 3: 完善 `runtime-notes.md`**

Must explain:

```text
why this bundle exists
why ppt still needs LibreOffice
why wheel versions are locked
how to use this bundle in intranet
```

- [ ] **Step 4: Commit**

```bash
git add ppt_offline_runtime/README.md ppt_offline_runtime/VERSION_MANIFEST.md ppt_offline_runtime/records/runtime-notes.md
git commit -m "docs: finalize ppt offline runtime bundle guide"
```

### Task 7: 最终验证与交付整理

**Files:**
- Verify only: `ppt_offline_runtime/**`
- Verify only: `backend/open_webui/retrieval/loaders/*.py`

- [ ] **Step 1: 重新运行 PowerPoint 单测**

Run:

```powershell
$env:PYTHONPATH='backend'; .\.venv\Scripts\python.exe -m pytest backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py -q --basetemp=.tmp-pytest-codex
```

Expected:

```text
6 passed
```

- [ ] **Step 2: 运行离线运行时校验脚本**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ppt_offline_runtime\scripts\verify_offline_runtime.ps1
```

Expected:

```text
verification completed successfully
```

- [ ] **Step 3: 查看最终目录状态**

Run:

```powershell
Get-ChildItem ppt_offline_runtime -Recurse | Select-Object FullName
```

Expected:

```text
Complete runtime bundle structure with wheels, scripts, records, and logs
```

- [ ] **Step 4: Commit**

```bash
git add ppt_offline_runtime backend/open_webui/retrieval/loaders/main.py backend/open_webui/retrieval/loaders/powerpoint_converter.py backend/open_webui/retrieval/loaders/powerpoint_fallback.py backend/open_webui/retrieval/loaders/powerpoint_markdown.py backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py start.py docs/superpowers/specs/2026-04-21-ppt-offline-runtime-bundle-design.md docs/superpowers/plans/2026-04-21-ppt-offline-runtime-bundle.md
git commit -m "feat: add ppt offline runtime bundle"
```
