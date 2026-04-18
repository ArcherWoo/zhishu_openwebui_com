# 启动运行时加固实施计划

> **给代理工作者：** 必须使用子技能 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐项落实本计划。步骤使用复选框语法（`- [ ]`）进行跟踪。

**目标：** 改进 `start.py`，让依赖缓存更准确、启动状态更可信、探测命令不会无限挂起，同时让前台关闭在控制台中断和服务式终止两种情况下都能干净完成。

**架构：** 保持现有启动脚本整体结构不变，但在四个边界上强化行为：依赖缓存签名、启动前校验、子进程健康观测，以及信号/探测处理。把共享的运行时生命周期逻辑集中在 `start.py` 中，扩展 `tests/test_start.py` 的定向回归测试，并避免无关重构。

**技术栈：** Python 3.11+、`subprocess`、`socket`、`signal`、`pytest`、基于 monkeypatch 的进程测试

---

### 任务 1：拆分后端与前端缓存签名

**文件：**
- 修改：`start.py`
- 测试：`tests/test_start.py`

- [ ] **步骤 1：编写失败中的缓存签名回归测试**

```python
def test_python_dependency_cache_signature_ignores_frontend_inputs(monkeypatch):
    monkeypatch.setattr(start, 'REQUIREMENTS_FILE', Path('C:/repo/backend/requirements.txt'))
    monkeypatch.setattr(start, 'PACKAGE_JSON', Path('C:/repo/package.json'))
    monkeypatch.setattr(start, 'PACKAGE_LOCK', Path('C:/repo/package-lock.json'))

    stat_map = {
        'C:/repo/backend/requirements.txt': SimpleNamespace(st_mtime_ns=11),
        'C:/repo/package.json': SimpleNamespace(st_mtime_ns=22),
        'C:/repo/package-lock.json': SimpleNamespace(st_mtime_ns=33),
    }

    monkeypatch.setattr(Path, 'stat', lambda self: stat_map[str(self)])

    assert start.python_requirements_signature() == {
        'requirements_mtime': '11',
    }


def test_node_dependency_cache_signature_tracks_only_node_inputs(monkeypatch):
    monkeypatch.setattr(start, 'PACKAGE_JSON', Path('C:/repo/package.json'))
    monkeypatch.setattr(start, 'PACKAGE_LOCK', Path('C:/repo/package-lock.json'))

    stat_map = {
        'C:/repo/package.json': SimpleNamespace(st_mtime_ns=22),
        'C:/repo/package-lock.json': SimpleNamespace(st_mtime_ns=33),
    }

    monkeypatch.setattr(Path, 'stat', lambda self: stat_map[str(self)])

    assert start.node_requirements_signature() == {
        'package_lock_mtime': '33',
        'package_json_mtime': '22',
    }
```

- [ ] **步骤 2：运行定向测试命令，确认因缺失辅助函数而失败**

运行：`$env:PYTHONPATH='backend'; python -m pytest tests/test_start.py -q`
预期：`FAIL`，并报出 `python_requirements_signature` / `node_requirements_signature` 缺失或缓存行为不正确。

- [ ] **步骤 3：实现拆分后的缓存签名辅助函数，并接入依赖检查**

```python
def python_requirements_signature() -> dict[str, str]:
    return {
        'requirements_mtime': str(REQUIREMENTS_FILE.stat().st_mtime_ns),
    }


def node_requirements_signature() -> dict[str, str]:
    return {
        'package_lock_mtime': str(PACKAGE_LOCK.stat().st_mtime_ns if PACKAGE_LOCK.exists() else 0),
        'package_json_mtime': str(PACKAGE_JSON.stat().st_mtime_ns if PACKAGE_JSON.exists() else 0),
    }
```

- [ ] **步骤 4：更新依赖安装路径，让它们使用新的签名**

```python
signature = python_requirements_signature()
expected = {
    'state_version': SCRIPT_STATE_VERSION,
    'base_python': str(Path(base_python).resolve()),
    'venv_python': str(venv_python.resolve()),
    **signature,
}
```

```python
expected = {
    'state_version': SCRIPT_STATE_VERSION,
    **node_requirements_signature(),
}
```

- [ ] **步骤 5：重新运行聚焦的回归测试**

运行：`$env:PYTHONPATH='backend'; python -m pytest tests/test_start.py -q`
预期：新的缓存签名测试通过，且现有启动测试没有回归。

### 任务 2：增加端口预检，并推迟“已启动”消息

**文件：**
- 修改：`start.py`
- 测试：`tests/test_start.py`

- [ ] **步骤 1：编写失败中的启动预检与启动日志测试**

```python
def test_launch_open_webui_checks_port_before_spawning(monkeypatch):
    prepared = start.PreparedRuntime(
        base_python='python',
        npm_executable='npm',
        pip_mirror=start.PipMirror(),
        npm_registry=start.NpmRegistry(),
        pip_env={},
        npm_env={},
        venv_python=Path('C:/fake/python.exe'),
        runtime_env={},
    )
    args = SimpleNamespace(host='0.0.0.0', port=8080)
    checked = []

    monkeypatch.setattr(start, 'ensure_port_available', lambda host, port: checked.append((host, port)))
    monkeypatch.setattr(start, 'build_uvicorn_command', lambda *_args, **_kwargs: ['python', '-m', 'uvicorn'])
    monkeypatch.setattr(start, 'run_managed_process', lambda *args, **kwargs: 0)
    monkeypatch.setattr(start.subprocess, 'Popen', lambda *args, **kwargs: SimpleNamespace(poll=lambda: 0))

    start.launch_open_webui(prepared, args)

    assert checked == [('0.0.0.0', 8080)]


def test_launch_open_webui_logs_started_only_after_child_survives_observation_window(monkeypatch, capsys):
    prepared = start.PreparedRuntime(
        base_python='python',
        npm_executable='npm',
        pip_mirror=start.PipMirror(),
        npm_registry=start.NpmRegistry(),
        pip_env={},
        npm_env={},
        venv_python=Path('C:/fake/python.exe'),
        runtime_env={},
    )
    args = SimpleNamespace(host='0.0.0.0', port=8080)

    monkeypatch.setattr(start, 'ensure_port_available', lambda *_args: None)
    monkeypatch.setattr(start, 'build_uvicorn_command', lambda *_args, **_kwargs: ['python', '-m', 'uvicorn'])
    monkeypatch.setattr(start, 'collect_lan_ipv4_addresses', lambda: [])
    monkeypatch.setattr(start, 'run_managed_process', lambda *args, **kwargs: 0)
    monkeypatch.setattr(
        start.subprocess,
        'Popen',
        lambda *args, **kwargs: SimpleNamespace(poll=lambda: None),
    )

    start.launch_open_webui(prepared, args)

    captured = capsys.readouterr()
    assert '[start] 准备启动 Open WebUI...' in captured.out
    assert '[start] Open WebUI 已启动。' in captured.out
```

- [ ] **步骤 2：运行相同测试命令，确认失败聚焦在启动时序**

运行：`$env:PYTHONPATH='backend'; python -m pytest tests/test_start.py -q`
预期：`FAIL` 指向 `ensure_port_available` 未被使用，以及启动日志时机不正确。

- [ ] **步骤 3：在 `start.py` 中复用生产环境的端口检查辅助函数**

```python
def ensure_port_available(host: str, port: int) -> None:
    bind_targets = []

    if host in {'0.0.0.0', ''}:
        bind_targets.append(('0.0.0.0', socket.AF_INET))
    elif host == '::':
        bind_targets.append(('::', socket.AF_INET6))
    else:
        infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in infos:
            bind_targets.append((sockaddr[0], family))

    for bind_host, family in bind_targets:
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            sock.bind((bind_host, port))
        finally:
            sock.close()
```

- [ ] **步骤 4：把前台启动日志改为“先准备，验证后再宣布已启动”**

```python
log('准备启动 Open WebUI...')
log(f'本机访问地址: {browser_url(args.host, args.port)}')
```

```python
if wait:
    ensure_port_available(args.host, args.port)
    process = subprocess.Popen(...)
    if process.poll() is None:
        log('Open WebUI 已启动。')
    run_managed_process(...)
```

- [ ] **步骤 5：重新运行启动相关回归测试**

运行：`$env:PYTHONPATH='backend'; python -m pytest tests/test_start.py -q`
预期：新的启动预检与“已启动”时机测试通过。

### 任务 3：为所有探测命令加上超时边界

**文件：**
- 修改：`start.py`
- 测试：`tests/test_start.py`

- [ ] **步骤 1：编写失败中的探测超时测试**

```python
def test_capture_returns_empty_string_when_probe_times_out(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd='python', timeout=kwargs['timeout'])

    monkeypatch.setattr(start.subprocess, 'run', fake_run)

    assert start.capture(['python', '--version']) == ''


def test_capture_uses_default_probe_timeout(monkeypatch):
    seen = {}

    def fake_run(*args, **kwargs):
        seen['timeout'] = kwargs['timeout']
        return SimpleNamespace(returncode=0, stdout='ok\\n', stderr='')

    monkeypatch.setattr(start.subprocess, 'run', fake_run)

    assert start.capture(['python', '--version']) == 'ok'
    assert seen['timeout'] == start.PROBE_COMMAND_TIMEOUT
```

- [ ] **步骤 2：运行定向测试命令，确认失败信息指向超时处理**

运行：`$env:PYTHONPATH='backend'; python -m pytest tests/test_start.py -q`
预期：`FAIL`，因为 `capture()` 还没有超时常量，也没有处理 timeout expired。

- [ ] **步骤 3：新增共享探测超时常量，并加固 `capture()`**

```python
PROBE_COMMAND_TIMEOUT = 10.0


def capture(
    cmd: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    timeout: float = PROBE_COMMAND_TIMEOUT,
) -> str:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        log(f'命令探测超时，已跳过: {shell_join(cmd)}')
        return ''

    if result.returncode != 0:
        return ''
    return result.stdout.strip()
```

- [ ] **步骤 4：除非确实需要更长时间，否则调用点都使用默认超时**

```python
output = capture([py_launcher, '-0p'])
registry = capture([npm_executable, 'config', 'get', 'registry'])
```

- [ ] **步骤 5：重新运行回归测试**

运行：`$env:PYTHONPATH='backend'; python -m pytest tests/test_start.py -q`
预期：探测超时相关测试通过，且现有启动测试全部保持通过。

### 任务 4：把优雅关闭扩展到服务式终止

**文件：**
- 修改：`start.py`
- 测试：`tests/test_start.py`

- [ ] **步骤 1：编写失败中的 `SIGTERM` 关闭测试**

```python
def test_install_managed_signal_handlers_includes_sigterm_on_non_windows(monkeypatch):
    handlers = []

    monkeypatch.setattr(start.os, 'name', 'posix')
    monkeypatch.setattr(start.threading, 'current_thread', start.threading.main_thread)
    monkeypatch.setattr(start.signal, 'getsignal', lambda signum: None)
    monkeypatch.setattr(start.signal, 'signal', lambda signum, handler: handlers.append(signum))

    start.install_managed_signal_handlers(lambda *_args: None)

    assert start.signal.SIGTERM in handlers


def test_build_managed_signal_handler_records_sigterm_shutdown(capsys):
    shutdown_requested = threading.Event()
    shutdown_state = {}

    handler = start.build_managed_signal_handler(
        object(),
        service_label='Open WebUI',
        shutdown_requested=shutdown_requested,
        shutdown_state=shutdown_state,
    )

    handler(start.signal.SIGTERM, None)

    assert shutdown_requested.is_set() is True
    assert shutdown_state == {'signal_name': 'SIGTERM'}
    captured = capsys.readouterr()
    assert '[start] 收到 SIGTERM 信号，正在优雅关闭 Open WebUI...' in captured.out
```

- [ ] **步骤 2：运行聚焦测试命令，确认失败信息指向缺失的 `SIGTERM` 覆盖**

运行：`$env:PYTHONPATH='backend'; python -m pytest tests/test_start.py -q`
预期：`FAIL`，因为当前非 Windows 管理信号中还没有包含 `SIGTERM`。

- [ ] **步骤 3：为非 Windows 关闭扩展托管信号安装逻辑**

```python
handled_signals = [signal.SIGINT]
if hasattr(signal, 'SIGBREAK'):
    handled_signals.append(signal.SIGBREAK)
if os.name != 'nt' and hasattr(signal, 'SIGTERM'):
    handled_signals.append(signal.SIGTERM)
```

- [ ] **步骤 4：继续把实际关闭动作保留在主轮询循环中执行**

```python
if shutdown_requested.is_set():
    shutdown_managed_process(
        process,
        service_label=service_label,
        use_ctrl_break=use_ctrl_break,
    )
```

- [ ] **步骤 5：重新运行完整的定向启动测试集**

运行：`$env:PYTHONPATH='backend'; python -m pytest tests/test_start.py tests/test_model_paths.py -q`
预期：所有启动/运行时加固回归测试均为绿色通过。

### 任务 5：验证并发布运行时加固改动

**文件：**
- 修改：`start.py`
- 修改：`tests/test_start.py`

- [ ] **步骤 1：运行完整的聚焦验证命令**

运行：`$env:PYTHONPATH='backend'; python -m pytest tests/test_start.py tests/test_model_paths.py -q`
预期：`32 passed` 或更高，且零失败。

- [ ] **步骤 2：检查暂存差异范围**

运行：`git diff -- start.py tests/test_start.py`
预期：差异只包含缓存签名、启动预检/日志、探测超时，以及 `SIGTERM` 关闭处理。

- [ ] **步骤 3：提交运行时加固工作**

```bash
git add start.py tests/test_start.py
git commit -m "fix: harden start runtime lifecycle"
```
