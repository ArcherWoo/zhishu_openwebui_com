# Pyodide 缓存复用实施计划

> **给代理工作者：** 必须使用子技能 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐项落实本计划。步骤使用复选框语法（`- [ ]`）进行跟踪。

**目标：** 让 `scripts/prepare-pyodide.js` 在本地完整缓存存在时复用缓存，而不是每次构建都重新下载 Pyodide 包。

**架构：** 引入一个纯缓存校验辅助模块，在主脚本发起任何网络请求之前，对运行时元数据、请求的包列表和必需文件进行比对。主脚本随后根据校验结果决定是跳过、补齐还是完全重置。

**技术栈：** Node.js、ESM、Vitest。

---

### 任务 1：新增缓存校验回归测试

**文件：**
- 创建：`scripts/lib/pyodide-cache.test.js`
- 创建：`scripts/lib/pyodide-cache.js`

- [ ] **步骤 1：编写失败中的校验测试**
- [ ] **步骤 2：运行 `npm run test:frontend -- --run scripts/lib/pyodide-cache.test.js`，确认新测试失败**
- [ ] **步骤 3：实现辅助模块，直到新测试通过**

### 任务 2：重构 `prepare-pyodide.js`

**文件：**
- 修改：`scripts/prepare-pyodide.js`

- [ ] **步骤 1：从 `node_modules/pyodide/package.json` 读取真实 Pyodide 版本**
- [ ] **步骤 2：在调用 `loadPyodide` 之前校验 `static/pyodide/`**
- [ ] **步骤 3：当缓存已经完整时跳过下载流程**
- [ ] **步骤 4：用 `rm` 替换已弃用的 `rmdir` 用法**
- [ ] **步骤 5：仅在刷新成功后持久化缓存元数据**

### 任务 3：端到端验证复用路径

**文件：**
- 修改：无

- [ ] **步骤 1：运行定向的 Vitest 回归测试**
- [ ] **步骤 2：先执行一次 `node scripts/prepare-pyodide.js`，修复缓存或写入元数据**
- [ ] **步骤 3：再次执行 `node scripts/prepare-pyodide.js`，确认命中缓存并走跳过路径**
- [ ] **步骤 4：运行 `npm run build`，确认构建路径仍然正常**
