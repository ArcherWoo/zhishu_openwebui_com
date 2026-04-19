# 警告与关闭清理实施计划

> **给代理工作者：** 必须使用子技能 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐项落实本计划。步骤使用复选框语法（`- [ ]`）进行跟踪。

**目标：** 清理真正有意义的前端构建警告，移除工具页面中的社区推荐卡片，并让 Windows 上的 `Ctrl+C` 关闭过程安静且优雅。

**架构：** 前端工作保持“外科手术式”范围：只修复构建输出中点名的、由项目自身组件产生的 Svelte 警告，并直接从页面组件移除不需要的工具页区块。后端关闭修复保持在 `start.py` 和测试里，通过现有启动器抽象隔离 Windows 进程组行为。

**技术栈：** Python、Pytest、Svelte、TypeScript、Vite。

---

### 任务 1：添加失败中的关闭回归测试

**文件：**
- 修改：`tests/test_start.py`
- 修改：`start.py`

- [ ] **步骤 1：编写失败中的测试**
- [ ] **步骤 2：运行 `.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q`，确认新增断言失败**
- [ ] **步骤 3：在 `start.py` 中实现 Windows 进程组优雅关闭改动**
- [ ] **步骤 4：再次运行 `.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q`，确认通过**

### 任务 2：移除工具社区卡片

**文件：**
- 修改：`src/lib/components/workspace/Tools.svelte`

- [ ] **步骤 1：在可行的地方添加 UI 回归测试或定向断言**
- [ ] **步骤 2：从工具页面移除底部社区推荐区块**
- [ ] **步骤 3：运行 `npm run build`，确认页面仍可正常编译**

### 任务 3：减少可操作的前端警告

**文件：**
- 修改：构建输出中报告警告的 Svelte 组件

- [ ] **步骤 1：通过 `npm run build` 采集当前警告列表**
- [ ] **步骤 2：修复项目自有组件中的图标按钮标签、自闭合非 void 标签、可点击静态元素，以及过期导出**
- [ ] **步骤 3：重新运行 `npm run build`，对比警告输出**
- [ ] **步骤 4：当剩余警告都属于第三方或已明确延期项时停止**

### 任务 4：最终验证

**文件：**
- 修改：无

- [ ] **步骤 1：运行 `.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q`**
- [ ] **步骤 2：运行 `npm run build`**
- [ ] **步骤 3：检查 `git status --short`，确认只改动了预期文件**
- [ ] **步骤 4：提交并推送**
