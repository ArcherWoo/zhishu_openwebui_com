# Pyodide 内网离线运行时实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让公司内网环境在缺少 `pyodide` npm 源包时，也能通过外网预打包资源顺利完成 `python start.py` 的前端安装与构建。

**Architecture:** 保留现有 `vendor/npm` 作为 npm 离线缓存入口，新增一套“外网打包、内网恢复”的 Release 附件流程。根目录新增 `pyodide_runtime/README.md` 作为中文操作入口，实际恢复目标仍然是 `vendor/npm/` 和 `static/pyodide/`，同时在 `start.py` 里补上更明确的离线提示。

**Tech Stack:** Python、PowerShell、npm、Pyodide、GitHub Release。

---

### Task 1: 启动期离线提示回归测试

**Files:**
- Modify: `tests/test_start.py`
- Modify: `start.py`

- [ ] **Step 1: 写失败测试，覆盖 npm 安装失败时的 Pyodide 离线提示触发**
- [ ] **Step 2: 运行定向 pytest，确认测试先失败**
- [ ] **Step 3: 实现最小代码，让 `ensure_frontend_dependencies()` 在需要时打印离线恢复指引**
- [ ] **Step 4: 重新运行定向 pytest，确认通过**

### Task 2: 前端构建失败时的 Pyodide 指引

**Files:**
- Modify: `tests/test_start.py`
- Modify: `start.py`

- [ ] **Step 1: 写失败测试，覆盖 `npm run build` 失败时的离线提示触发**
- [ ] **Step 2: 运行定向 pytest，确认测试先失败**
- [ ] **Step 3: 实现最小代码，让 `ensure_frontend_build()` 在需要时输出相同恢复路径**
- [ ] **Step 4: 重新运行定向 pytest，确认通过**

### Task 3: 离线打包与恢复脚本

**Files:**
- Create: `scripts/package-pyodide-release.ps1`
- Create: `scripts/restore-pyodide-release.ps1`
- Modify: `.gitignore`

- [ ] **Step 1: 新增 PowerShell 打包脚本，把 `vendor/npm/` 和 `static/pyodide/` 打成 Release 附件 zip**
- [ ] **Step 2: 新增恢复脚本，把 zip 解压回仓库正确目录**
- [ ] **Step 3: 调整 `.gitignore`，避免离线大资源误入 Git**
- [ ] **Step 4: 手工跑一轮脚本帮助信息或最小 smoke，确认路径与输出合理**

### Task 4: 中文操作文档

**Files:**
- Create: `pyodide_runtime/README.md`
- Modify: `scripts/README.md`

- [ ] **Step 1: 编写根目录中文 README，说明为什么 `pyodide` 不能直接照搬 `nltk_data/` 模式**
- [ ] **Step 2: 写清楚外网打包、GitHub Release 上传、内网恢复、启动验证四段流程**
- [ ] **Step 3: 在 `scripts/README.md` 增补新脚本用途与命令**

### Task 5: 最终验证

**Files:**
- Modify: 无

- [ ] **Step 1: 运行 `pytest tests\\test_start.py -q -p no:cacheprovider`**
- [ ] **Step 2: 视资源情况执行脚本帮助或最小打包/恢复 smoke**
- [ ] **Step 3: 汇总内网部署时应带入的文件与使用顺序**
