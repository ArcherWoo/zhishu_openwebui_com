# 启动脚本中文体验实施计划

> **给代理工作者：** 必须使用子技能 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐项落实本计划。步骤使用复选框语法（`- [ ]`）进行跟踪。

**目标：** 让 `start.py` 与 `start_prod.py` 在中文环境下更易操作，打印正确的 localhost/局域网访问地址，在 `Ctrl+C` 时优雅关闭，并补充面向 Windows 与 Linux 的中文部署说明。

**架构：** 保持运行时绑定行为不变（`0.0.0.0` 仍是默认 host），但将面向用户的状态输出与子进程生命周期管理收敛到 `start.py` 内的共享辅助函数中。`start_prod.py` 复用这些辅助函数，让两个脚本呈现一致的中文体验与优雅关闭行为。

**技术栈：** Python 3.11+、subprocess、socket/ipaddress 辅助函数、pytest、Markdown 文档

---

### 任务 1：扩展启动体验的回归测试

**文件：**
- 修改：`tests/test_start.py`

- [ ] **步骤 1：为局域网 URL 展示和优雅关闭辅助函数编写失败中的测试**

```python
def test_collect_lan_urls_prefers_private_ipv4_addresses(monkeypatch):
    ...


def test_run_managed_process_logs_graceful_shutdown_and_returns_130(monkeypatch, capsys):
    ...


def test_start_prod_run_cli_exits_cleanly_on_keyboard_interrupt(monkeypatch, capsys):
    ...
```

- [ ] **步骤 2：运行测试，确认它们因预期缺失行为而失败**

运行：`.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q`
预期：失败信息指向缺失的辅助函数或不匹配的日志输出

- [ ] **步骤 3：保持测试聚焦于行为**

只覆盖：
- localhost/局域网 URL 生成
- 子进程优雅关闭路径
- `start_prod.py` 顶层 `KeyboardInterrupt` 处理

- [ ] **步骤 4：再次运行同一测试命令，确认失败范围仍然聚焦**

运行：`.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q`
预期：仍然是同一组聚焦失败，不出现无关的导入错误

### 任务 2：在 `start.py` 中实现共享中文状态与优雅关闭

**文件：**
- 修改：`start.py`
- 测试：`tests/test_start.py`

- [ ] **步骤 1：为中文日志、局域网 URL 计算和子进程关闭添加最小辅助函数**

可以增加如下聚焦辅助函数：
- `browser_url()`
- `collect_lan_ipv4_addresses()`
- `format_access_urls()`
- `terminate_process_gracefully()`
- `run_managed_process()`

- [ ] **步骤 2：让 `start.py` 使用这些新辅助函数，同时不改动 CLI 参数**

要求行为：
- 保持绑定 host 不变
- 打印中文启动状态
- 同时显示 localhost URL 和局域网 URL
- 显式托管前台子进程
- 在 `Ctrl+C` 时优雅停止，超时回退，并返回退出码 `130`

- [ ] **步骤 3：为关键区块补充中文注释**

给以下部分加注释：
- Python 重新执行
- 虚拟环境准备
- 依赖安装缓存
- 运行时环境组装
- 局域网 URL 展示
- 优雅关闭流程

- [ ] **步骤 4：运行定向测试**

运行：`.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q`
预期：所有测试通过

### 任务 3：在 `start_prod.py` 中复用同样的体验与关闭流程

**文件：**
- 修改：`start_prod.py`
- 测试：`tests/test_start.py`

- [ ] **步骤 1：让 `start_prod.py` 接入 `start.py` 的共享辅助函数**

要求行为：
- 生产模式的前台启动也使用托管子进程等待
- 分离/服务模式保持原样
- 启动提示改为中文
- localhost/局域网 URL 展示与 `start.py` 保持一致

- [ ] **步骤 2：为生产特有逻辑补充中文注释**

说明：
- 生产默认值
- 端口预检
- 分离模式日志
- Windows 服务管理路径

- [ ] **步骤 3：补充或调整测试，覆盖生产包装器行为**

运行：`.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q`
预期：与生产相关的测试也通过

### 任务 4：编写中文部署文档

**文件：**
- 创建：`docs/DEPLOY_START_SCRIPTS_ZH.md`

- [ ] **步骤 1：编写实用的中文部署指南**

需要包含的章节：
- `start.py` 与 `start_prod.py`
- Windows 部署
- Linux 部署
- 局域网访问说明
- 优雅关闭说明
- 故障排查

- [ ] **步骤 2：包含常见用法的精确命令**

给出这些场景的具体示例：
- 首次运行
- 生产运行
- detach 模式
- Windows 服务操作
- Windows/Linux 端口检查

- [ ] **步骤 3：明确说明 `0.0.0.0` 与浏览器访问地址的区别**

需要包含这一规则：
- 绑定地址可以是 `0.0.0.0`
- 浏览器应使用 `localhost` 或打印出来的局域网地址

### 任务 5：端到端验证

**文件：**
- 修改：`start.py`
- 修改：`start_prod.py`
- 修改：`tests/test_start.py`
- 创建：`docs/DEPLOY_START_SCRIPTS_ZH.md`

- [ ] **步骤 1：运行聚焦的回归测试**

运行：`.\.venv\Scripts\python.exe -m pytest tests/test_start.py`
预期：所有测试通过

- [ ] **步骤 2：对 `start.py` 的启动文案做冒烟测试**

运行：`C:\Python313\python.exe start.py --backend-only`
预期：中文启动输出中包含 localhost，以及在可用时包含局域网地址

- [ ] **步骤 3：对 `start_prod.py` 的启动文案做冒烟测试**

运行：`C:\Python313\python.exe start_prod.py --prepare-only`
预期：出现中文生产引导输出，且没有 traceback

- [ ] **步骤 4：确认文档文件存在且可读**

运行：`Get-Content docs\DEPLOY_START_SCRIPTS_ZH.md -TotalCount 80`
预期：可以看到中文部署指南内容
