# Pyodide 缓存复用设计

## 目标

避免 `scripts/prepare-pyodide.js` 在本地缓存已经完整时，仍然在每次构建都重新下载整套 Pyodide 包。

## 问题

- 脚本当前拿缓存中的版本去和 `package.json` 中的 semver 范围比较，而不是和真实安装的 `node_modules/pyodide` 版本比较。
- 脚本总是在判断缓存是否可复用之前就进入 Pyodide 安装流程。
- 脚本使用了已弃用的 `fs.rmdir(..., { recursive: true })` 来删除缓存。
- 当前没有持久化的缓存元数据来描述哪些 PyPI wheel 已成功镜像。

## 期望行为

- 从 `node_modules/pyodide/package.json` 读取真实安装的 Pyodide 版本。
- 在调用 `loadPyodide` 之前先校验 `static/pyodide/`。
- 当缓存完整时，完全跳过抓取/安装流程。
- 只有当缓存中的 Pyodide 运行时版本过期时，才清空 `static/pyodide/`。
- 在刷新成功后持久化缓存元数据，供后续运行安全复用。

## 设计

### 缓存元数据

在成功刷新后写入 `static/pyodide/open-webui-pyodide-cache.json`。该文件包含：

- Schema 版本
- 已安装的 Pyodide 版本
- 请求的 Pyodide 包列表
- 请求的 PyPI wheel 包列表
- 已下载的 PyPI wheel 文件名列表

### 校验规则

只有在以下条件全部满足时，缓存才可复用：

- 缓存元数据存在，并且与当前请求的包集合一致。
- 缓存中的 Pyodide 版本与 `node_modules/pyodide` 一致。
- `node_modules/pyodide` 的所有核心文件都存在于 `static/pyodide` 中。
- 缓存元数据中记录的所有 wheel 文件名都存在于 `static/pyodide` 中。

### 刷新规则

- 如果缓存的运行时版本过期，使用 `fs.rm(..., { recursive: true, force: true })` 删除 `static/pyodide/`。
- 如果元数据缺失或不完整，但运行时版本仍然是当前版本，则保留目录并进行补齐。
- 只有当 Pyodide 和 PyPI 的下载步骤都成功时，才写入缓存元数据。

## 测试策略

- 为缓存校验增加一个小型纯辅助模块。
- 添加 Vitest 回归覆盖，验证：
  - 成功复用缓存
  - 版本不匹配导致失效
  - 缺失 wheel 导致失效
  - 包列表不匹配导致失效

## 成功标准

- 第一次修复性运行会重建或补齐缓存，并写入元数据。
- 第二次运行会打印缓存命中消息，并跳过高开销的安装流程。
- 递归删除缓存时不再出现弃用警告。
