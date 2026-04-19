# 预取进度反馈实施计划

> **给代理工作者：** 必须使用子技能 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐项落实本计划。步骤使用复选框语法（`- [ ]`）进行跟踪。

**目标：** 让 `prefetch_vendor_deps.py` 显示实时进度、心跳以及可选的详细子进程输出，同时保留现有的最终报告能力。

**架构：** 在 `prefetch_vendor_deps.py` 内增加一个带跟踪能力的子进程运行器，让所有长时间运行的包操作都通过它执行，并用聚焦的单元测试覆盖用户可见行为。

**技术栈：** Python 3.11、`subprocess`、`threading`、`pytest`

---

### 任务 1：用测试锁定期望的终端行为

**文件：**
- 修改：`tests/test_start.py`
- 修改：`prefetch_vendor_deps.py`

- [ ] **步骤 1：为 `--verbose` 解析和跟踪命令日志编写失败中的测试**
- [ ] **步骤 2：运行聚焦的 pytest 选择，确认测试失败**
- [ ] **步骤 3：实现最小辅助函数和参数接线**
- [ ] **步骤 4：再次运行聚焦的 pytest 选择，确认测试通过**

### 任务 2：在 Python 与 NPM 阶段接入跟踪进度

**文件：**
- 修改：`prefetch_vendor_deps.py`

- [ ] **步骤 1：让 Python 包循环通过带阶段标签的跟踪运行器执行**
- [ ] **步骤 2：让 NPM 包循环和校验也通过跟踪运行器执行**
- [ ] **步骤 3：增加简洁的阶段开始日志，并保持失败收集行为不变**
- [ ] **步骤 4：再次运行聚焦的 pytest 选择**

### 任务 3：验证用户体验并记录新参数

**文件：**
- 修改：`VENDOR_DEPLOYMENT_MANUAL.md`
- 修改：`prefetch_vendor_deps.py`

- [ ] **步骤 1：执行一次真实的 `--dry-run`，检查终端输出**
- [ ] **步骤 2：更新部署手册，记录新的进度/verbose 行为**
- [ ] **步骤 3：重新运行测试和 dry-run 命令**
- [ ] **步骤 4：提交并推送**
