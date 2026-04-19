from __future__ import annotations

import argparse
import ipaddress
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

try:
    import ctypes
    from ctypes import wintypes
except ImportError:
    ctypes = None
    wintypes = None


"""
Open WebUI 通用启动脚本。

在仓库根目录执行 `python start.py` 后，脚本会自动完成：
1. 检查并切换到受支持的 Python 版本
2. 创建或修复虚拟环境
3. 检测 pip 与 npm 镜像配置
4. 安装后端与前端依赖
5. 在需要时构建前端，并启动 uvicorn

如果是偏部署场景的启动方式，优先使用 `start_prod.py`。
"""


# 统一维护启动脚本用到的关键路径，避免后续逻辑到处重复拼接。
ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / 'backend'
REQUIREMENTS_FILE = BACKEND_DIR / 'requirements.txt'
PACKAGE_JSON = ROOT / 'package.json'
PACKAGE_LOCK = ROOT / 'package-lock.json'
BUILD_DIR = ROOT / 'build'
STATE_FILE = ROOT / '.start-state.json'
BUILD_MARKER = BUILD_DIR / '.built-by-start'
VENDOR_DIR = ROOT / 'vendor'
PYTHON_VENDOR_DIR = VENDOR_DIR / 'python'
NPM_VENDOR_DIR = VENDOR_DIR / 'npm'
VENDOR_REPORT_JSON = VENDOR_DIR / 'report.json'
VENDOR_REPORT_MD = VENDOR_DIR / 'report.md'
PYODIDE_RUNTIME_DIR = ROOT / 'pyodide_runtime'
PYODIDE_STATIC_DIR = ROOT / 'static' / 'pyodide'
PYODIDE_LOCK_FILE = PYODIDE_STATIC_DIR / 'pyodide-lock.json'
PYODIDE_RESTORE_SCRIPT = ROOT / 'scripts' / 'restore-pyodide-release.ps1'
PYODIDE_RUNTIME_README = PYODIDE_RUNTIME_DIR / 'README.md'
SCRIPT_STATE_VERSION = 1
GRACEFUL_STOP_TIMEOUT = 8.0
MANAGED_PROCESS_POLL_INTERVAL = 0.2
PROBE_COMMAND_TIMEOUT = 10.0


# 启动脚本自己的状态输出统一走这里，方便后面整体切换风格。
def log(message: str) -> None:
    print(f'[start] {message}', flush=True)


# 统一错误出口，保证终端看到的是明确的人类可读信息。
def fail(message: str, exit_code: int = 1) -> None:
    print(f'[start] 错误: {message}', file=sys.stderr, flush=True)
    raise SystemExit(exit_code)


def shell_join(parts: Iterable[str]) -> str:
    return subprocess.list2cmdline(list(parts))


# 把绑定地址转换成用户真正应该在浏览器里访问的地址。
# 例如 `0.0.0.0` 适合服务监听，但浏览器应访问 `localhost`。
def browser_url(host: str, port: int) -> str:
    if host in {'0.0.0.0', '::', '[::]'}:
        host = 'localhost'
    elif ':' in host and not host.startswith('['):
        host = f'[{host}]'

    return f'http://{host}:{port}'


def is_private_ipv4_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False

    return (
        isinstance(address, ipaddress.IPv4Address)
        and address.is_private
        and not address.is_loopback
        and not address.is_link_local
    )


def lan_ip_priority(value: str) -> tuple[int, str]:
    if value.startswith('192.168.'):
        return (0, value)
    if value.startswith('172.'):
        return (1, value)
    if value.startswith('10.'):
        return (2, value)
    return (99, value)


def collect_lan_ipv4_addresses() -> list[str]:
    candidates: list[str] = []
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None)
    except socket.gaierror:
        return []

    seen: set[str] = set()
    for family, _, _, _, sockaddr in infos:
        if family != socket.AF_INET:
            continue

        host = sockaddr[0]
        if not is_private_ipv4_address(host) or host in seen:
            continue

        seen.add(host)
        candidates.append(host)

    return sorted(candidates, key=lan_ip_priority)


def log_access_urls(host: str, port: int) -> None:
    log('Open WebUI 已启动。')
    log(f'本机访问地址: {browser_url(host, port)}')

    lan_addresses = collect_lan_ipv4_addresses()
    if not lan_addresses:
        log('未检测到可用的局域网 IPv4 地址，当前请优先使用本机地址访问。')
        return

    for lan_ip in lan_addresses:
        log(f'局域网访问地址: http://{lan_ip}:{port}')


def terminate_process_gracefully(
    process: subprocess.Popen,
    *,
    service_label: str,
    timeout: float = GRACEFUL_STOP_TIMEOUT,
    use_ctrl_break: bool = False,
) -> int | None:
    poll = getattr(process, 'poll', None)
    if callable(poll):
        current_returncode = poll()
        if current_returncode is not None:
            return current_returncode

    try:
        if use_ctrl_break and os.name == 'nt':
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()
    except ProcessLookupError:
        return process.returncode

    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        log(f'{service_label} 在 {int(timeout)} 秒内未退出，正在强制结束...')
        if os.name == 'nt':
            subprocess.run(
                ['taskkill', '/PID', str(process.pid), '/T', '/F'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        process.kill()
        try:
            return process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return process.returncode


def build_managed_signal_handler(
    process: subprocess.Popen,
    *,
    service_label: str,
    use_ctrl_break: bool = False,
    shutdown_requested: threading.Event | None = None,
    shutdown_state: dict[str, str] | None = None,
):
    def handler(signum, _frame):
        if shutdown_requested is not None:
            if shutdown_requested.is_set():
                return
            shutdown_requested.set()

        signal_name = signal.Signals(signum).name if signum in signal.Signals._value2member_map_ else str(signum)
        if shutdown_state is not None:
            shutdown_state.setdefault('signal_name', signal_name)
        log(f'收到 {signal_name} 信号，正在优雅关闭 {service_label}...')

    return handler


def build_managed_console_handler(
    process: subprocess.Popen,
    *,
    service_label: str,
    use_ctrl_break: bool = False,
    shutdown_requested: threading.Event | None = None,
    shutdown_state: dict[str, str] | None = None,
):
    handled_events = {
        0: 'CTRL_C_EVENT',
        1: 'CTRL_BREAK_EVENT',
        2: 'CTRL_CLOSE_EVENT',
        5: 'CTRL_LOGOFF_EVENT',
        6: 'CTRL_SHUTDOWN_EVENT',
    }

    def handler(ctrl_type: int) -> bool:
        if ctrl_type not in handled_events:
            return False

        if shutdown_requested is not None:
            if shutdown_requested.is_set():
                return True
            shutdown_requested.set()

        signal_name = handled_events[ctrl_type]
        if shutdown_state is not None:
            shutdown_state.setdefault('signal_name', signal_name)

        log(f'收到 {signal_name}，正在优雅关闭 {service_label}...')
        return True

    return handler


def install_managed_signal_handlers(handler) -> dict[int, object]:
    if threading.current_thread() is not threading.main_thread():
        return {}

    previous_handlers: dict[int, object] = {}
    handled_signals = [signal.SIGINT]
    if hasattr(signal, 'SIGBREAK'):
        handled_signals.append(signal.SIGBREAK)

    for handled_signal in handled_signals:
        previous_handlers[handled_signal] = signal.getsignal(handled_signal)
        signal.signal(handled_signal, handler)

    return previous_handlers


def restore_managed_signal_handlers(previous_handlers: dict[int, object]) -> None:
    for handled_signal, previous_handler in previous_handlers.items():
        signal.signal(handled_signal, previous_handler)


def install_windows_console_handler(handler):
    if os.name != 'nt' or ctypes is None or wintypes is None:
        return None

    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
    callback = callback_type(lambda ctrl_type: bool(handler(ctrl_type)))
    ctypes.windll.kernel32.SetConsoleCtrlHandler(callback, True)
    return callback


def restore_windows_console_handler(callback) -> None:
    if os.name == 'nt' and callback is not None and ctypes is not None:
        ctypes.windll.kernel32.SetConsoleCtrlHandler(callback, False)


def shutdown_managed_process(
    process: subprocess.Popen,
    *,
    service_label: str,
    use_ctrl_break: bool = False,
) -> None:
    terminate_process_gracefully(
        process,
        service_label=service_label,
        use_ctrl_break=use_ctrl_break,
    )
    log(f'{service_label} 已停止。')
    raise SystemExit(130)


def run_managed_process(
    process: subprocess.Popen,
    *,
    service_label: str,
    command: list[str] | None = None,
    use_ctrl_break: bool = False,
) -> int:
    shutdown_requested = threading.Event()
    shutdown_state: dict[str, str] = {}

    signal_handler = build_managed_signal_handler(
        process,
        service_label=service_label,
        use_ctrl_break=use_ctrl_break,
        shutdown_requested=shutdown_requested,
        shutdown_state=shutdown_state,
    )
    previous_handlers = install_managed_signal_handlers(signal_handler)
    console_callback = None

    if os.name == 'nt':
        console_handler = build_managed_console_handler(
            process,
            service_label=service_label,
            use_ctrl_break=use_ctrl_break,
            shutdown_requested=shutdown_requested,
            shutdown_state=shutdown_state,
        )
        console_callback = install_windows_console_handler(console_handler)

    try:
        while True:
            if shutdown_requested.is_set():
                shutdown_managed_process(
                    process,
                    service_label=service_label,
                    use_ctrl_break=use_ctrl_break,
                )

            return_code = process.poll()
            if return_code is not None:
                break

            time.sleep(MANAGED_PROCESS_POLL_INTERVAL)
    except KeyboardInterrupt:
        log(f'收到中断信号，正在优雅关闭 {service_label}...')
        shutdown_managed_process(
            process,
            service_label=service_label,
            use_ctrl_break=use_ctrl_break,
        )
    finally:
        restore_windows_console_handler(console_callback)
        restore_managed_signal_handlers(previous_handlers)

    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command or [])

    return return_code


def run(
    cmd: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    log(f'执行命令: {shell_join(cmd)}')
    return subprocess.run(cmd, cwd=str(cwd), env=env, check=check)


def capture(
    cmd: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return ''
    return result.stdout.strip()


def file_text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


# 当前项目官方支持 Python 3.11 和 3.12。
def is_supported_python(version: tuple[int, int, int]) -> bool:
    return (3, 11) <= version < (3, 13)


def current_python_version() -> tuple[int, int, int]:
    return (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)


def interpreter_version(executable: str) -> tuple[int, int, int] | None:
    output = capture(
        [
            executable,
            '-c',
            'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")',
        ]
    )
    if not output:
        return None
    try:
        major, minor, micro = output.split('.')
        return int(major), int(minor), int(micro)
    except ValueError:
        return None


# 按多个来源探测可用的 Python：
# 1. 环境变量
# 2. PATH
# 3. Windows 的 `py` 启动器
# 4. `uv python list`
def discover_python_candidates() -> list[str]:
    candidates: list[str] = []

    for env_key in ['OPEN_WEBUI_PYTHON', 'PYTHON']:
        value = os.environ.get(env_key, '').strip()
        if value:
            candidates.append(value)

    for command in ['python3.12', 'python3.11', 'python']:
        resolved = shutil.which(command)
        if resolved:
            candidates.append(resolved)

    if os.name == 'nt':
        py_launcher = shutil.which('py')
        if py_launcher:
            output = capture([py_launcher, '-0p'])
            for line in output.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                candidate = parts[-1]
                if candidate.lower().endswith('.exe'):
                    candidates.append(candidate)

    uv_executable = shutil.which('uv')
    if uv_executable:
        output = capture([uv_executable, 'python', 'list'])
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            candidate = parts[-1]
            if candidate.lower().endswith('.exe'):
                candidates.append(candidate)

    unique_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = os.path.normcase(os.path.abspath(candidate))
        if normalized not in seen and Path(candidate).exists():
            seen.add(normalized)
            unique_candidates.append(candidate)

    return unique_candidates


def maybe_reexec_with_supported_python(
    args: argparse.Namespace,
    *,
    script_path: Path | None = None,
    forwarded_args: list[str] | None = None,
) -> None:
    # 当前 Python 版本不符合要求时，自动切换到合适的解释器重新执行脚本。
    version = current_python_version()
    if is_supported_python(version) or args.allow_unsupported_python:
        if not is_supported_python(version):
            log(
                f'当前 Python {version[0]}.{version[1]}.{version[2]} 不在官方支持范围内，'
                '但由于传入了 --allow-unsupported-python，脚本将继续执行。'
            )
        return

    if os.environ.get('OPEN_WEBUI_START_REEXEC') == '1':
        fail(
            f'当前解释器版本为 Python {version[0]}.{version[1]}.{version[2]}。'
            'Open WebUI 需要 Python 3.11 或 3.12。'
        )

    supported: list[tuple[tuple[int, int, int], str]] = []
    for candidate in discover_python_candidates():
        candidate_version = interpreter_version(candidate)
        if not candidate_version:
            continue
        if is_supported_python(candidate_version):
            supported.append((candidate_version, candidate))

    if not supported:
        fail(
            f'当前解释器版本为 Python {version[0]}.{version[1]}.{version[2]}，但 Open WebUI 需要 '
            'Python 3.11 或 3.12。请先安装受支持的版本，或在你明确接受风险时传入 '
            '--allow-unsupported-python 继续执行。'
        )

    supported.sort(reverse=True)
    best_version, best_python = supported[0]
    env = os.environ.copy()
    env['OPEN_WEBUI_START_REEXEC'] = '1'
    target_script = script_path or Path(__file__).resolve()
    target_args = forwarded_args if forwarded_args is not None else sys.argv[1:]
    log(f'检测到可用的 Python {best_version[0]}.{best_version[1]}.{best_version[2]}，正在切换: {best_python}')
    raise SystemExit(subprocess.call([best_python, str(target_script), *target_args], env=env))


# 在 Windows 上优先寻找 `npm.cmd`，避免直接调 `npm` 时命令解析异常。
def npm_command() -> str:
    for env_key in ['OPEN_WEBUI_NPM_CMD', 'NPM']:
        value = os.environ.get(env_key, '').strip()
        if value:
            return value

    candidates = ['npm.cmd', 'npm'] if os.name == 'nt' else ['npm']
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    fail('未找到 npm。请先安装 Node.js，并确认 npm 已加入 PATH。')


def pip_config_value(python_executable: str, key: str) -> str:
    return capture([python_executable, '-m', 'pip', 'config', 'get', key])


@dataclass
class PipMirror:
    index_url: str | None = None
    extra_index_url: str | None = None
    trusted_host: str | None = None
    index_source: str | None = None
    extra_source: str | None = None
    trusted_source: str | None = None


# 读取 pip 镜像配置。
# 优先级：
# 1. 环境变量
# 2. `pip config`
def discover_pip_mirror(python_executable: str) -> PipMirror:
    mirror = PipMirror()

    env_candidates = [
        ('OPEN_WEBUI_PIP_INDEX_URL', 'index_url', 'index_source'),
        ('PIP_INDEX_URL', 'index_url', 'index_source'),
        ('UV_INDEX_URL', 'index_url', 'index_source'),
        ('OPEN_WEBUI_PIP_EXTRA_INDEX_URL', 'extra_index_url', 'extra_source'),
        ('PIP_EXTRA_INDEX_URL', 'extra_index_url', 'extra_source'),
        ('OPEN_WEBUI_PIP_TRUSTED_HOST', 'trusted_host', 'trusted_source'),
        ('PIP_TRUSTED_HOST', 'trusted_host', 'trusted_source'),
    ]
    for env_key, field_name, source_name in env_candidates:
        value = os.environ.get(env_key, '').strip()
        if value and getattr(mirror, field_name) is None:
            setattr(mirror, field_name, value)
            setattr(mirror, source_name, f'env:{env_key}')

    config_keys = [
        ('global.index-url', 'index_url', 'index_source'),
        ('site.index-url', 'index_url', 'index_source'),
        ('user.index-url', 'index_url', 'index_source'),
        ('global.extra-index-url', 'extra_index_url', 'extra_source'),
        ('site.extra-index-url', 'extra_index_url', 'extra_source'),
        ('user.extra-index-url', 'extra_index_url', 'extra_source'),
        ('global.trusted-host', 'trusted_host', 'trusted_source'),
        ('site.trusted-host', 'trusted_host', 'trusted_source'),
        ('user.trusted-host', 'trusted_host', 'trusted_source'),
    ]
    for config_key, field_name, source_name in config_keys:
        if getattr(mirror, field_name) is not None:
            continue
        value = pip_config_value(python_executable, config_key).strip()
        if value:
            setattr(mirror, field_name, value)
            setattr(mirror, source_name, f'pip-config:{config_key}')

    if mirror.index_url and not mirror.trusted_host:
        parsed = urlparse(mirror.index_url)
        if parsed.scheme == 'http' and parsed.netloc:
            mirror.trusted_host = parsed.netloc
            mirror.trusted_source = 'derived-from-index-url'

    return mirror


@dataclass
class NpmRegistry:
    registry: str | None = None
    source: str | None = None


@dataclass
class PreparedRuntime:
    # 环境准备完成后，把后续启动要用到的信息统一装进这个对象里返回。
    base_python: str
    npm_executable: str
    pip_mirror: PipMirror
    npm_registry: NpmRegistry
    pip_env: dict[str, str]
    npm_env: dict[str, str]
    venv_python: Path
    runtime_env: dict[str, str]


# 读取 npm registry 配置。
# 环境变量优先级高于 `npm config get registry`。
def discover_npm_registry(npm_executable: str) -> NpmRegistry:
    for env_key in ['OPEN_WEBUI_NPM_REGISTRY', 'NPM_CONFIG_REGISTRY', 'npm_config_registry']:
        value = os.environ.get(env_key, '').strip()
        if value:
            return NpmRegistry(registry=value, source=f'env:{env_key}')

    registry = capture([npm_executable, 'config', 'get', 'registry'])
    if registry and registry.lower() != 'undefined':
        return NpmRegistry(registry=registry, source='npm-config')

    return NpmRegistry()


def build_pip_env(mirror: PipMirror) -> dict[str, str]:
    env = os.environ.copy()
    if mirror.index_url:
        env['PIP_INDEX_URL'] = mirror.index_url
    if mirror.extra_index_url:
        env['PIP_EXTRA_INDEX_URL'] = mirror.extra_index_url
    if mirror.trusted_host:
        env['PIP_TRUSTED_HOST'] = mirror.trusted_host
    return env


def build_npm_env(registry: NpmRegistry) -> dict[str, str]:
    env = os.environ.copy()
    if registry.registry:
        env['npm_config_registry'] = registry.registry
        env['NPM_CONFIG_REGISTRY'] = registry.registry
    env.setdefault('CYPRESS_INSTALL_BINARY', '0')
    return env


# `pyvenv.cfg` 会记录虚拟环境对应的解释器信息。
# 这里用它判断当前 `.venv` 是否还能安全复用。
def parse_pyvenv_cfg(pyvenv_cfg: Path) -> dict[str, str]:
    if not pyvenv_cfg.exists():
        return {}

    values: dict[str, str] = {}
    for line in pyvenv_cfg.read_text(encoding='utf-8').splitlines():
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip().lower()] = value.strip()
    return values


def same_path(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


# 检查现有虚拟环境是否匹配当前选中的 Python。
# 不匹配时直接重建，避免在错误环境上继续安装依赖。
def venv_matches_base_python(base_python: str, venv_dir: Path, venv_python: Path) -> bool:
    if not venv_python.exists():
        return False

    cfg = parse_pyvenv_cfg(venv_dir / 'pyvenv.cfg')
    if not cfg:
        return False

    cfg_executable = cfg.get('executable')
    if cfg_executable and not same_path(cfg_executable, base_python):
        return False

    base_version = interpreter_version(base_python)
    venv_version = interpreter_version(str(venv_python))
    if base_version and venv_version and venv_version[:2] != base_version[:2]:
        return False

    cfg_version = cfg.get('version', '')
    if base_version and cfg_version and not cfg_version.startswith(f'{base_version[0]}.{base_version[1]}.'):
        return False

    return True


def recreate_venv(venv_dir: Path) -> None:
    if venv_dir.exists():
        log(f'检测到虚拟环境与当前 Python 不兼容，正在删除: {venv_dir}')
        shutil.rmtree(venv_dir)


# 较老的 pip 在较新的 Python 版本上容易出问题，因此这里做一个简单门槛检查。
def pip_needs_upgrade(base_python: str, pip_version_output: str) -> bool:
    if not pip_version_output:
        return True

    base_version = interpreter_version(base_python)
    if base_version and base_version >= (3, 13, 0):
        return True

    parts = pip_version_output.split()
    if len(parts) < 2:
        return True

    version_text = parts[1]
    major_text = version_text.split('.', 1)[0]
    try:
        major = int(major_text)
    except ValueError:
        return True
    return major < 24


# 确保虚拟环境存在，并且内部的打包工具链可用。
# 如果 pip / setuptools / wheel 太旧，就顺手升级。
def ensure_venv(base_python: str, venv_dir: Path, pip_env: dict[str, str]) -> Path:
    venv_python = venv_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')

    if venv_dir.exists() and not venv_matches_base_python(base_python, venv_dir, venv_python):
        recreate_venv(venv_dir)

    if not venv_python.exists():
        log(f'正在创建虚拟环境: {venv_dir}')
        run([base_python, '-m', 'venv', str(venv_dir), '--without-pip'], env=pip_env)

    pip_version = capture([str(venv_python), '-m', 'pip', '--version'])
    if pip_version and pip_needs_upgrade(base_python, pip_version):
        log('正在升级虚拟环境中的 pip / setuptools / wheel...')
        run(
            [
                base_python,
                '-m',
                'pip',
                '--python',
                str(venv_python),
                'install',
                '--upgrade',
                'pip',
                'setuptools',
                'wheel',
            ],
            env=pip_env,
        )
        pip_version = capture([str(venv_python), '-m', 'pip', '--version'])

    if pip_version:
        return venv_python

    bundled_pip = capture(
        [
            base_python,
            '-c',
            (
                'import ensurepip; from pathlib import Path; '
                "wheel = next((Path(ensurepip.__file__).resolve().parent / '_bundled').glob('pip-*.whl')); "
                'print(wheel)'
            ),
        ]
    )
    if not bundled_pip:
        fail('无法找到用于引导虚拟环境的内置 pip wheel。')

    log('正在为虚拟环境引导安装 pip...')
    run([base_python, '-m', 'pip', '--python', str(venv_python), 'install', bundled_pip], env=pip_env)

    pip_version = capture([str(venv_python), '-m', 'pip', '--version'])
    if pip_needs_upgrade(base_python, pip_version):
        log('正在升级虚拟环境中的 pip / setuptools / wheel...')
        run(
            [
                base_python,
                '-m',
                'pip',
                '--python',
                str(venv_python),
                'install',
                '--upgrade',
                'pip',
                'setuptools',
                'wheel',
            ],
            env=pip_env,
        )
    return venv_python


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(file_text(STATE_FILE))
    except json.JSONDecodeError:
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True), encoding='utf-8')


# 用文件修改时间做一个轻量级依赖缓存，避免每次都全量重装。
def requirements_signature() -> dict[str, str]:
    return {
        'requirements_mtime': str(REQUIREMENTS_FILE.stat().st_mtime_ns),
        'package_lock_mtime': str(PACKAGE_LOCK.stat().st_mtime_ns if PACKAGE_LOCK.exists() else 0),
        'package_json_mtime': str(PACKAGE_JSON.stat().st_mtime_ns if PACKAGE_JSON.exists() else 0),
    }


def frontend_inputs() -> list[Path]:
    return [
        PACKAGE_JSON,
        PACKAGE_LOCK,
        ROOT / 'vite.config.ts',
        ROOT / 'svelte.config.js',
        ROOT / 'tailwind.config.js',
        ROOT / 'postcss.config.js',
        ROOT / 'src' / 'tailwind.css',
        ROOT / 'scripts' / 'prepare-pyodide.js',
    ]


def latest_mtime(path: Path) -> float:
    latest = 0.0
    for child in path.rglob('*'):
        try:
            latest = max(latest, child.stat().st_mtime)
        except OSError:
            continue
    return latest


def vendor_dir_has_files(path: Path) -> bool:
    if not path.exists():
        return False

    for child in path.rglob('*'):
        if child.is_file():
            return True
    return False


def build_python_install_commands(
    venv_python: Path,
    vendor_dir: Path,
    requirements_file: Path,
) -> tuple[list[str], list[str]]:
    local_only_command = [
        str(venv_python),
        '-m',
        'pip',
        'install',
        '--no-index',
        '--find-links',
        str(vendor_dir),
        '-r',
        str(requirements_file),
    ]
    fallback_command = [
        str(venv_python),
        '-m',
        'pip',
        'install',
        '--find-links',
        str(vendor_dir),
        '-r',
        str(requirements_file),
    ]
    return local_only_command, fallback_command


def build_python_requirement_install_commands(
    venv_python: Path,
    vendor_dir: Path,
    requirement: str,
) -> tuple[list[str], list[str]]:
    local_only_command = [
        str(venv_python),
        '-m',
        'pip',
        'install',
        '--no-index',
        '--find-links',
        str(vendor_dir),
        requirement,
    ]
    fallback_command = [
        str(venv_python),
        '-m',
        'pip',
        'install',
        '--find-links',
        str(vendor_dir),
        requirement,
    ]
    return local_only_command, fallback_command


def build_npm_install_commands(
    npm_executable: str,
    vendor_dir: Path,
) -> tuple[list[str], list[str]]:
    cache_dir = str(vendor_dir)
    local_only_command = [npm_executable, 'ci', '--cache', cache_dir, '--offline']
    fallback_command = [npm_executable, 'ci', '--cache', cache_dir, '--prefer-offline']
    return local_only_command, fallback_command


def run_with_vendor_fallback(
    local_only_command: list[str],
    fallback_command: list[str],
    *,
    vendor_dir: Path,
    env: dict[str, str],
    local_label: str,
    fallback_label: str,
) -> None:
    vendor_dir.mkdir(parents=True, exist_ok=True)

    if vendor_dir_has_files(vendor_dir):
        try:
            run(local_only_command, env=env)
            return
        except subprocess.CalledProcessError:
            log(f'{local_label} 未完全命中本地 vendor 目录，正在回退到 {fallback_label}...')
    else:
        log(f'未检测到可用的本地 vendor 缓存，直接使用 {fallback_label}。')

    run(fallback_command, env=env)


# 判断前端产物是否过期，过期才重新构建。
def frontend_needs_build() -> bool:
    if not BUILD_DIR.exists() or not BUILD_MARKER.exists():
        return True

    marker_time = BUILD_MARKER.stat().st_mtime
    watched = [ROOT / 'src', ROOT / 'static', *frontend_inputs()]
    for item in watched:
        if not item.exists():
            continue
        item_time = latest_mtime(item) if item.is_dir() else item.stat().st_mtime
        if item_time > marker_time:
            return True
    return False


def ensure_backend_dependencies(
    venv_python: Path,
    base_python: str,
    args: argparse.Namespace,
    pip_env: dict[str, str],
) -> None:
    # 只有依赖输入变化，或明确传入强制参数时，才重新安装后端依赖。
    state = load_state()
    signature = requirements_signature()
    cached = state.get('python', {})
    expected = {
        'state_version': SCRIPT_STATE_VERSION,
        'base_python': str(Path(base_python).resolve()),
        'venv_python': str(venv_python.resolve()),
        **signature,
    }

    if args.force_python_install or cached != expected:
        local_only_command, fallback_command = build_python_install_commands(
            venv_python,
            PYTHON_VENDOR_DIR,
            REQUIREMENTS_FILE,
        )
        run_with_vendor_fallback(
            local_only_command,
            fallback_command,
            vendor_dir=PYTHON_VENDOR_DIR,
            env=pip_env,
            local_label='后端 Python 依赖安装',
            fallback_label='镜像源或在线 pip 安装',
        )

        if interpreter_version(str(venv_python)) and interpreter_version(str(venv_python)) >= (3, 13, 0):
            local_only_command, fallback_command = build_python_requirement_install_commands(
                venv_python,
                PYTHON_VENDOR_DIR,
                'audioop-lts',
            )
            run_with_vendor_fallback(
                local_only_command,
                fallback_command,
                vendor_dir=PYTHON_VENDOR_DIR,
                env=pip_env,
                local_label='audioop-lts 本地安装',
                fallback_label='镜像源或在线 pip 安装',
            )

        state['python'] = expected
        save_state(state)
    else:
        log('后端 Python 依赖未发生变化，跳过 pip 安装。')


def ensure_frontend_dependencies(
    npm_executable: str,
    args: argparse.Namespace,
    npm_env: dict[str, str],
) -> None:
    # 纯后端模式不应该触碰 Node.js 依赖。
    if args.backend_only:
        log('检测到 --backend-only，跳过 npm ci。')
        return

    state = load_state()
    cached = state.get('node', {})
    expected = {
        'state_version': SCRIPT_STATE_VERSION,
        'package_lock_mtime': str(PACKAGE_LOCK.stat().st_mtime_ns if PACKAGE_LOCK.exists() else 0),
        'package_json_mtime': str(PACKAGE_JSON.stat().st_mtime_ns if PACKAGE_JSON.exists() else 0),
    }

    if args.force_node_install or cached != expected or not (ROOT / 'node_modules').exists():
        local_only_command, fallback_command = build_npm_install_commands(
            npm_executable,
            NPM_VENDOR_DIR,
        )
        run_with_vendor_fallback(
            local_only_command,
            fallback_command,
            vendor_dir=NPM_VENDOR_DIR,
            env=npm_env,
            local_label='前端 npm 本地缓存安装',
            fallback_label='镜像源或在线 npm 安装',
        )
        state['node'] = expected
        save_state(state)
    else:
        log('前端 Node.js 依赖未发生变化，跳过 npm ci。')


def ensure_frontend_build(
    npm_executable: str,
    args: argparse.Namespace,
    npm_env: dict[str, str],
) -> None:
    # 纯后端模式不需要构建前端资源。
    if args.backend_only:
        log('检测到 --backend-only，跳过前端构建。')
        return

    if args.force_frontend_build or frontend_needs_build():
        try:
            run([npm_executable, 'run', 'build'], env=npm_env)
        except subprocess.CalledProcessError:
            if should_log_pyodide_offline_guidance():
                log_pyodide_offline_guidance('npm run build')
            raise
        BUILD_DIR.mkdir(parents=True, exist_ok=True)
        BUILD_MARKER.write_text('built by start.py\n', encoding='utf-8')
    else:
        log('前端构建产物未过期，跳过 npm run build。')


# 生产运行需要稳定的密钥。
# 如果环境里没有提供，就在 `backend/` 下自动生成并复用。
def ensure_secret_key(runtime_env: dict[str, str]) -> None:
    if runtime_env.get('WEBUI_SECRET_KEY') or runtime_env.get('WEBUI_JWT_SECRET_KEY'):
        return

    key_file = runtime_env.get('WEBUI_SECRET_KEY_FILE')
    key_path = Path(key_file) if key_file else BACKEND_DIR / '.webui_secret_key'

    if key_path.exists():
        key = key_path.read_text(encoding='utf-8').strip()
    else:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key = secrets.token_urlsafe(32)
        key_path.write_text(key, encoding='utf-8')
        log(f'已生成 WEBUI_SECRET_KEY 文件: {key_path}')

    runtime_env['WEBUI_SECRET_KEY'] = key


def build_runtime_env(
    venv_python: Path,
    args: argparse.Namespace,
    pip_mirror: PipMirror,
    npm_registry: NpmRegistry,
) -> dict[str, str]:
    # 这里统一拼出最终交给 uvicorn 的运行环境变量。
    # `start.py` 与 `start_prod.py` 都走这一套逻辑。
    env = os.environ.copy()
    env['PYTHONPATH'] = str(BACKEND_DIR)
    env.setdefault('ENV', 'prod')
    env.setdefault('HOST', args.host)
    env.setdefault('PORT', str(args.port))
    env.setdefault('USER_AGENT', 'open-webui-start.py')
    env.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
    env.setdefault('RAG_EMBEDDING_MODEL_AUTO_UPDATE', 'False')
    env.setdefault('RAG_RERANKING_MODEL_AUTO_UPDATE', 'False')

    embedding_model_dir = str((ROOT / 'embedding_model').resolve())
    nltk_data_dir = str((ROOT / 'nltk_data').resolve())
    decrypt_output_dir = str((ROOT / 'backend' / 'data' / 'uploads' / 'decrypted').resolve())
    env.setdefault('EMBEDDING_MODEL_DIR', embedding_model_dir)
    env.setdefault('SENTENCE_TRANSFORMERS_HOME', embedding_model_dir)
    env.setdefault('HF_HOME', embedding_model_dir)
    env.setdefault('NLTK_DATA', nltk_data_dir)
    env.setdefault('AUTO_DOWNLOAD_NLTK', 'False')
    env.setdefault('ENABLE_UPLOAD_DECRYPTION', 'True')
    env.setdefault('DECRYPT_SERVER_URL', '')
    env.setdefault('DECRYPT_TIMEOUT_SECONDS', '120')
    env.setdefault('DECRYPT_OUTPUT_DIR', decrypt_output_dir)

    if getattr(args, 'online', False):
        env.pop('OFFLINE_MODE', None)
        env.pop('HF_HUB_OFFLINE', None)
        env.pop('TRANSFORMERS_OFFLINE', None)
    else:
        env.setdefault('OFFLINE_MODE', 'True')
        env.setdefault('HF_HUB_OFFLINE', '1')
        env.setdefault('TRANSFORMERS_OFFLINE', '1')
        env.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')

    if not args.enable_base_model_cache and 'ENABLE_BASE_MODELS_CACHE' not in env:
        env['ENABLE_BASE_MODELS_CACHE'] = 'False'

    if pip_mirror.index_url:
        env.setdefault('PIP_INDEX_URL', pip_mirror.index_url)
    if pip_mirror.extra_index_url:
        env.setdefault('PIP_EXTRA_INDEX_URL', pip_mirror.extra_index_url)
    if pip_mirror.trusted_host:
        env.setdefault('PIP_TRUSTED_HOST', pip_mirror.trusted_host)

    if npm_registry.registry:
        env.setdefault('NPM_CONFIG_REGISTRY', npm_registry.registry)
        env.setdefault('npm_config_registry', npm_registry.registry)

    ensure_secret_key(env)
    return env


def build_uvicorn_command(
    venv_python: Path,
    args: argparse.Namespace,
    runtime_env: dict[str, str],
) -> list[str]:
    # 把最终的 uvicorn 启动命令集中在这里，保证不同入口的启动形状一致。
    command = [
        str(venv_python),
        '-m',
        'open_webui.uvicorn_runner',
        '--host',
        args.host,
        '--port',
        str(args.port),
    ]

    forwarded_allow_ips = runtime_env.get('FORWARDED_ALLOW_IPS', '').strip()
    if forwarded_allow_ips and not (os.name == 'nt' and forwarded_allow_ips == '*'):
        command.extend(['--forwarded-allow-ips', forwarded_allow_ips])

    uvicorn_workers = runtime_env.get('UVICORN_WORKERS', '').strip()
    if uvicorn_workers:
        command.extend(['--workers', uvicorn_workers])

    ws_mode = runtime_env.get('UVICORN_WS', '').strip()
    if ws_mode:
        command.extend(['--ws', ws_mode])

    return command


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='在仓库根目录完成依赖准备并启动 Open WebUI。',
    )
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', default=4173, type=int)
    parser.add_argument('--venv-dir', default='.venv')
    parser.add_argument('--backend-only', action='store_true')
    parser.add_argument('--force-python-install', action='store_true')
    parser.add_argument('--force-node-install', action='store_true')
    parser.add_argument('--force-frontend-build', action='store_true')
    parser.add_argument('--enable-base-model-cache', action='store_true')
    parser.add_argument('--online', action='store_true')
    parser.add_argument('--allow-unsupported-python', action='store_true')
    return parser.parse_args(argv)


def print_environment_summary(
    base_python: str,
    venv_python: Path,
    pip_mirror: PipMirror,
    npm_registry: NpmRegistry,
) -> None:
    log(f'当前使用的基础 Python: {base_python}')
    log(f'当前使用的虚拟环境 Python: {venv_python}')

    if pip_mirror.index_url:
        log(f'当前 pip 镜像: {pip_mirror.index_url} ({pip_mirror.index_source})')
    else:
        log('未检测到自定义 pip 镜像，后续将使用默认配置。')

    if pip_mirror.extra_index_url:
        log(f'当前 pip 附加镜像: {pip_mirror.extra_index_url} ({pip_mirror.extra_source})')

    if pip_mirror.trusted_host:
        log(f'当前 pip trusted host: {pip_mirror.trusted_host} ({pip_mirror.trusted_source})')

    if npm_registry.registry:
        log(f'当前 npm registry: {npm_registry.registry} ({npm_registry.source})')
    else:
        log('未检测到自定义 npm registry，后续将使用默认配置。')


# 这是开发脚本与生产脚本共用的准备阶段。
# 它负责准备 Python、Node、前端构建和运行环境，但暂时不启动 uvicorn。
def prepare_runtime(args: argparse.Namespace) -> PreparedRuntime:
    base_python = sys.executable
    npm_executable = npm_command()
    pip_mirror = discover_pip_mirror(base_python)
    npm_registry = discover_npm_registry(npm_executable)

    pip_env = build_pip_env(pip_mirror)
    npm_env = build_npm_env(npm_registry)

    venv_dir = (ROOT / args.venv_dir).resolve()
    venv_python = ensure_venv(base_python, venv_dir, pip_env)
    print_environment_summary(base_python, venv_python, pip_mirror, npm_registry)

    ensure_backend_dependencies(venv_python, base_python, args, pip_env)
    ensure_frontend_dependencies(npm_executable, args, npm_env)
    ensure_frontend_build(npm_executable, args, npm_env)

    runtime_env = build_runtime_env(venv_python, args, pip_mirror, npm_registry)

    return PreparedRuntime(
        base_python=base_python,
        npm_executable=npm_executable,
        pip_mirror=pip_mirror,
        npm_registry=npm_registry,
        pip_env=pip_env,
        npm_env=npm_env,
        venv_python=venv_python,
        runtime_env=runtime_env,
    )


def launch_open_webui(
    prepared: PreparedRuntime,
    args: argparse.Namespace,
    *,
    stdout=None,
    stderr=None,
    creationflags: int = 0,
    wait: bool = True,
):
    command = build_uvicorn_command(prepared.venv_python, args, prepared.runtime_env)
    managed_creationflags = creationflags
    use_ctrl_break = False

    if wait and os.name == 'nt':
        managed_creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
        use_ctrl_break = True

    # 前台模式下我们显式托管子进程，这样才能在 Ctrl+C 时先优雅关闭，再兜底强制结束。
    log_access_urls(args.host, args.port)
    log(f'启动命令: {shell_join(command)}')

    if wait:
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=prepared.runtime_env,
            stdout=stdout,
            stderr=stderr,
            creationflags=managed_creationflags,
        )
        run_managed_process(
            process,
            service_label='Open WebUI',
            command=command,
            use_ctrl_break=use_ctrl_break,
        )
        return subprocess.CompletedProcess(command, 0)

    return subprocess.Popen(
        command,
        cwd=str(ROOT),
        env=prepared.runtime_env,
        stdout=stdout,
        stderr=stderr,
        creationflags=creationflags,
    )


# 默认脚本真正的公共入口。
def python_requirements_signature() -> dict[str, str]:
    return {
        'requirements_mtime': str(REQUIREMENTS_FILE.stat().st_mtime_ns),
    }


def node_requirements_signature() -> dict[str, str]:
    return {
        'package_lock_mtime': str(PACKAGE_LOCK.stat().st_mtime_ns if PACKAGE_LOCK.exists() else 0),
        'package_json_mtime': str(PACKAGE_JSON.stat().st_mtime_ns if PACKAGE_JSON.exists() else 0),
    }


def frontend_node_modules_complete() -> bool:
    node_modules_dir = ROOT / 'node_modules'
    if not node_modules_dir.exists():
        return False

    required_markers = [
        node_modules_dir / 'pyodide' / 'package.json',
        node_modules_dir / '@sveltejs' / 'kit' / 'package.json',
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_markers if not path.exists()]

    if missing:
        log(f'妫€娴嬪埌涓嶅畬鏁寸殑 node_modules锛岀己灏? {", ".join(missing)}锛屽皢閲嶆柊鎵ц npm ci銆?')
        return False

    return True


def should_log_pyodide_offline_guidance() -> bool:
    node_pyodide_package = ROOT / 'node_modules' / 'pyodide' / 'package.json'
    return (not node_pyodide_package.exists()) or (not PYODIDE_LOCK_FILE.exists())


def format_pyodide_offline_guidance(*, stage: str) -> list[str]:
    return [
        f'{stage} 失败，检测到当前仓库缺少完整的 Pyodide 离线资源。',
        '公司内网部署请先在外网机器准备 Pyodide Release 附件，再恢复到当前仓库：',
        f'- npm 离线缓存目录：{NPM_VENDOR_DIR}',
        f'- Pyodide 运行时目录：{PYODIDE_STATIC_DIR}',
        f'- 恢复脚本：powershell -ExecutionPolicy Bypass -File "{PYODIDE_RESTORE_SCRIPT}" -ArchivePath "<zip路径>"',
        f'- 详细说明：{PYODIDE_RUNTIME_README}',
    ]


def log_pyodide_offline_guidance(stage: str) -> None:
    for line in format_pyodide_offline_guidance(stage=stage):
        log(line)


def requirements_signature() -> dict[str, str]:
    return {
        **python_requirements_signature(),
        **node_requirements_signature(),
    }


def install_managed_signal_handlers(handler) -> dict[int, object]:
    if threading.current_thread() is not threading.main_thread():
        return {}

    previous_handlers: dict[int, object] = {}
    handled_signals = [signal.SIGINT]
    if hasattr(signal, 'SIGBREAK'):
        handled_signals.append(signal.SIGBREAK)
    if os.name != 'nt' and hasattr(signal, 'SIGTERM'):
        handled_signals.append(signal.SIGTERM)

    for handled_signal in handled_signals:
        previous_handlers[handled_signal] = signal.getsignal(handled_signal)
        signal.signal(handled_signal, handler)

    return previous_handlers


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


def python_environment_signature(venv_python: Path, base_python: str) -> dict[str, str]:
    return {
        'base_python': str(Path(base_python).resolve()),
        'venv_python': str(venv_python.resolve()),
        'venv_python_mtime': str(venv_python.stat().st_mtime_ns if venv_python.exists() else 0),
    }


def ensure_backend_dependencies(
    venv_python: Path,
    base_python: str,
    args: argparse.Namespace,
    pip_env: dict[str, str],
) -> None:
    state = load_state()
    cached = state.get('python', {})
    expected = {
        'state_version': SCRIPT_STATE_VERSION,
        **python_environment_signature(venv_python, base_python),
        **python_requirements_signature(),
    }

    if args.force_python_install or cached != expected:
        local_only_command, fallback_command = build_python_install_commands(
            venv_python,
            PYTHON_VENDOR_DIR,
            REQUIREMENTS_FILE,
        )
        run_with_vendor_fallback(
            local_only_command,
            fallback_command,
            vendor_dir=PYTHON_VENDOR_DIR,
            env=pip_env,
            local_label='后端 Python 依赖安装',
            fallback_label='镜像源或在线 pip 安装',
        )

        version = interpreter_version(str(venv_python))
        if version and version >= (3, 13, 0):
            local_only_command, fallback_command = build_python_requirement_install_commands(
                venv_python,
                PYTHON_VENDOR_DIR,
                'audioop-lts',
            )
            run_with_vendor_fallback(
                local_only_command,
                fallback_command,
                vendor_dir=PYTHON_VENDOR_DIR,
                env=pip_env,
                local_label='audioop-lts 本地安装',
                fallback_label='镜像源或在线 pip 安装',
            )

        state['python'] = expected
        save_state(state)
    else:
        log('后端 Python 依赖未发生变化，跳过 pip 安装。')


def ensure_frontend_dependencies(
    npm_executable: str,
    args: argparse.Namespace,
    npm_env: dict[str, str],
) -> None:
    if args.backend_only:
        log('检测到 --backend-only，跳过 npm ci。')
        return

    state = load_state()
    cached = state.get('node', {})
    expected = {
        'state_version': SCRIPT_STATE_VERSION,
        **node_requirements_signature(),
    }

    if args.force_node_install or cached != expected or not frontend_node_modules_complete():
        local_only_command, fallback_command = build_npm_install_commands(
            npm_executable,
            NPM_VENDOR_DIR,
        )
        try:
            run_with_vendor_fallback(
                local_only_command,
                fallback_command,
                vendor_dir=NPM_VENDOR_DIR,
                env=npm_env,
                local_label='前端 npm 本地缓存安装',
                fallback_label='镜像源或在线 npm 安装',
            )
        except subprocess.CalledProcessError:
            if should_log_pyodide_offline_guidance():
                log_pyodide_offline_guidance('npm ci')
            raise
        state['node'] = expected
        save_state(state)
    else:
        log('前端 Node.js 依赖未发生变化，跳过 npm ci。')


def log_access_urls(host: str, port: int) -> None:
    log(f'本机访问地址: {browser_url(host, port)}')

    lan_addresses = collect_lan_ipv4_addresses()
    if not lan_addresses:
        log('未检测到可用的局域网 IPv4 地址，当前请优先使用本机地址访问。')
        return

    for lan_ip in lan_addresses:
        log(f'局域网访问地址: http://{lan_ip}:{port}')


def ensure_port_available(host: str, port: int) -> None:
    bind_targets: list[tuple[str, int]] = []

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


def launch_open_webui(
    prepared: PreparedRuntime,
    args: argparse.Namespace,
    *,
    stdout=None,
    stderr=None,
    creationflags: int = 0,
    wait: bool = True,
):
    command = build_uvicorn_command(prepared.venv_python, args, prepared.runtime_env)
    managed_creationflags = creationflags
    use_ctrl_break = False

    if wait and os.name == 'nt':
        managed_creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
        use_ctrl_break = True

    log('准备启动 Open WebUI...')
    log(f'启动命令: {shell_join(command)}')

    if wait:
        ensure_port_available(args.host, args.port)
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=prepared.runtime_env,
            stdout=stdout,
            stderr=stderr,
            creationflags=managed_creationflags,
        )
        if process.poll() is None:
            log('Open WebUI 已启动。')
            log_access_urls(args.host, args.port)
        run_managed_process(
            process,
            service_label='Open WebUI',
            command=command,
            use_ctrl_break=use_ctrl_break,
        )
        return subprocess.CompletedProcess(command, 0)

    return subprocess.Popen(
        command,
        cwd=str(ROOT),
        env=prepared.runtime_env,
        stdout=stdout,
        stderr=stderr,
        creationflags=creationflags,
    )


def bootstrap_and_run(args: argparse.Namespace) -> None:
    prepared = prepare_runtime(args)
    launch_open_webui(prepared, args)


def main(argv: list[str] | None = None) -> None:
    os.chdir(ROOT)
    args = parse_args(argv)

    maybe_reexec_with_supported_python(
        args,
        script_path=Path(__file__).resolve(),
        forwarded_args=argv if argv is not None else sys.argv[1:],
    )
    bootstrap_and_run(args)


def run_cli(argv: list[str] | None = None) -> None:
    try:
        main(argv)
    except KeyboardInterrupt:
        log('收到中断信号，正在停止服务...')
        raise SystemExit(130)


if __name__ == '__main__':
    run_cli()
