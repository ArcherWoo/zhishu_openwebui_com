# 启动运行时加固设计说明

**日期：** 2026-04-15  
**状态：** 已实现  
**对应计划：** `docs/superpowers/plans/2026-04-15-start-runtime-hardening.md`

## 背景

`start.py` 同时承担了开发环境启动、依赖准备、启动状态输出和前台关闭处理等职责。原先这条链路能用，但还存在四个容易在公司内网和长期维护中放大的问题：

1. Python 依赖缓存和 Node 依赖缓存共用一套签名，前端依赖改动会误伤后端缓存命中。
2. 前台启动时会过早打印“已启动”，一旦子进程刚拉起就退出，日志会误导排查。
3. 多个探测命令没有统一超时，局部环境异常时可能把启动流程挂住。
4. 非 Windows 场景下只处理了 `SIGINT`，服务式停止时常见的 `SIGTERM` 没有纳入同一套优雅关闭流程。

本次加固只修这四个边界，不做无关重构。

## 设计目标

1. 让 Python 与 Node 依赖缓存各自只追踪自己的输入文件。
2. 让“Open WebUI 已启动”只在子进程通过首轮存活检查后输出。
3. 给所有共享探测命令加默认超时，超时后记录日志并安全降级。
4. 让前台托管关闭逻辑同时覆盖控制台中断和非 Windows 的 `SIGTERM`。

## 方案

### 1. 拆分依赖缓存签名

新增两个辅助函数：

- `python_requirements_signature()`
- `node_requirements_signature()`

其中：

- Python 缓存只追踪 `backend/requirements.txt`
- Node 缓存只追踪 `package.json` 和 `package-lock.json`

`ensure_backend_dependencies()` 和 `ensure_frontend_dependencies()` 分别改用各自的签名写入 `.start-state.json`，避免前后端依赖状态互相污染。

### 2. 启动前端口预检与延后宣布“已启动”

新增 `ensure_port_available(host, port)`，在前台 `launch_open_webui(..., wait=True)` 中先做端口可绑定性检查，再实际拉起 `uvicorn` 子进程。

日志时序调整为：

1. 输出“准备启动 Open WebUI...”
2. 输出启动命令
3. 先做端口预检
4. 启动子进程
5. 只有当 `process.poll()` 仍为 `None` 时，才输出“Open WebUI 已启动。”以及访问地址

这样如果子进程秒退，就不会先给出误导性的成功日志。

### 3. 为共享探测命令增加默认超时

新增常量：

- `PROBE_COMMAND_TIMEOUT = 10.0`

`capture()` 改为统一接受 `timeout` 参数，默认使用该常量。  
当探测超时时：

- 记录一条明确日志
- 返回空字符串
- 不让超时异常直接中断整个启动准备流程

这样 `py -0p`、`uv python list`、`pip config get`、`npm config get registry` 等共享探测调用都自动获得超时保护。

### 4. 将 SIGTERM 纳入托管关闭流程

`install_managed_signal_handlers()` 在非 Windows 下新增 `SIGTERM` 注册，仍然保持原有设计：

- 信号处理函数只负责记录状态和设置 `shutdown_requested`
- 真正的关闭动作仍在主轮询里调用 `shutdown_managed_process()`

这样可以避免在异步信号上下文里直接做复杂清理，同时兼容服务式停止。

## 影响范围

**代码文件**

- `start.py`
- `tests/test_start.py`

**行为变化**

- 依赖缓存命中更准确
- 前台启动日志更可信
- 探测命令默认有超时边界
- 非 Windows 下 `SIGTERM` 会走与 `SIGINT` 一致的优雅关闭路径

**不受影响**

- `start.py` 的整体入口结构
- `start_prod.py` 的生产启动组织方式
- 依赖安装与前端构建的原有主流程

## 测试策略

新增或更新的回归测试覆盖以下行为：

- Python 缓存签名忽略前端输入
- Node 缓存签名只追踪前端输入
- 启动前会先做端口预检
- “已启动”日志只在子进程首轮存活后输出
- `capture()` 超时后返回空字符串
- `capture()` 使用统一默认超时
- 非 Windows 下安装托管信号时包含 `SIGTERM`

## 实施结果

本设计对应改动已经在当前工作区实现，并通过定向启动测试验证。
