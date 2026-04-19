# 2026-04-20 可选 Pyodide 构建方案

## 背景

公司内网环境已经具备 `vendor/npm`、`vendor/pip`、`nltk_data`、`embedding_model` 等离线部署条件，但前端构建仍会因为 `pyodide` npm 包缺失而失败，导致 `python start.py` 无法启动。

当前短期目标不是启用代码执行，而是先保证系统在没有 Pyodide 的情况下也能正常构建、启动和使用。

## 目标

1. 前端 `build/dev` 不再强制执行 `pyodide:fetch`
2. 即使本地没有安装 `pyodide` npm 包，也不会在构建阶段直接报错
3. 后端默认关闭代码执行和代码解释器
4. 前端相关入口在默认关闭时不再误触发 Pyodide 依赖
5. 保留未来补齐离线 Pyodide 资源后重新开启的能力

## 实施步骤

1. 先补回归测试，锁定“Pyodide 不再是构建强依赖”的目标行为
2. 修改 `package.json`，将 `pyodide:fetch` 从 `dev/build` 链路中移除
3. 修改 `scripts/prepare-pyodide.js`，改成可选执行、默认不联网下载
4. 修改 Pyodide worker，改为运行时从 `/pyodide/pyodide.mjs` 动态加载
5. 调整后端默认配置，关闭 `ENABLE_CODE_EXECUTION` 与 `ENABLE_CODE_INTERPRETER`
6. 跑测试与前端构建验证

## 验收标准

1. `npm run build` 在未安装 `pyodide` npm 包时不因静态依赖报错
2. `python start.py` 不会在前端构建阶段因为 Pyodide 缺失而失败
3. 默认配置下，普通聊天、知识库、笔记、工作空间等功能不受影响
4. 后续补齐 `static/pyodide` 后，管理员仍可按需重新开启代码执行能力
