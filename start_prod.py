from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import start


"""
Open WebUI 生产环境启动脚本。

它复用了 `start.py` 中的大部分环境准备逻辑，并额外提供：
1. 默认使用独立的 `.venv-prod` 虚拟环境
2. 支持后台分离启动与日志文件落盘
3. 支持 Windows 服务的安装、启动、停止与卸载

常见用法：
    python start_prod.py
    python start_prod.py --detach
    python start_prod.py --install-service
"""


ROOT = Path(__file__).resolve().parent
DEFAULT_LOG_DIR = ROOT / 'logs'
SERVICE_DIR = ROOT / 'service'
SERVICE_CONFIG = SERVICE_DIR / 'open_webui-service.json'
SERVICE_SCRIPT = ROOT / 'open_webui_windows_service.py'


def log(message: str) -> None:
    print(f'[start_prod] {message}', flush=True)


def fail(message: str, exit_code: int = 1) -> None:
    print(f'[start_prod] 错误: {message}', file=sys.stderr, flush=True)
    raise SystemExit(exit_code)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='使用偏生产环境的默认配置准备并启动 Open WebUI。',
    )
    parser.add_argument('--host', default=os.environ.get('HOST', '0.0.0.0'))
    parser.add_argument('--port', default=int(os.environ.get('PORT', '8080')), type=int)
    parser.add_argument('--venv-dir', default='.venv-prod')
    parser.add_argument('--data-dir', default=str(ROOT / 'backend' / 'data'))
    parser.add_argument('--secret-key-file', default=str(ROOT / 'backend' / '.webui_secret_key'))
    parser.add_argument('--cors-origin', default=os.environ.get('CORS_ALLOW_ORIGIN', ''))
    parser.add_argument('--log-dir', default=str(DEFAULT_LOG_DIR))
    parser.add_argument('--workers', default=os.environ.get('UVICORN_WORKERS', '1'))
    parser.add_argument('--forwarded-allow-ips', default=os.environ.get('FORWARDED_ALLOW_IPS', '*'))
    parser.add_argument('--ws-mode', default=os.environ.get('UVICORN_WS', 'auto'))
    parser.add_argument('--force-python-install', action='store_true')
    parser.add_argument('--force-node-install', action='store_true')
    parser.add_argument('--force-frontend-build', action='store_true')
    parser.add_argument('--enable-base-model-cache', action='store_true')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--online', action='store_true')
    parser.add_argument('--detach', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--allow-unsupported-python', action='store_true')

    parser.add_argument('--install-service', action='store_true')
    parser.add_argument('--remove-service', action='store_true')
    parser.add_argument('--start-service', action='store_true')
    parser.add_argument('--stop-service', action='store_true')
    parser.add_argument('--service-name', default='OpenWebUI')
    parser.add_argument('--service-display-name', default='Open WebUI')
    parser.add_argument(
        '--service-description',
        default='Open WebUI production service managed by start_prod.py',
    )
    parser.add_argument('--service-startup', choices=['auto', 'demand', 'disabled'], default='auto')
    return parser.parse_args(argv)


def build_start_namespace(args: argparse.Namespace) -> argparse.Namespace:
    # 把生产脚本的参数映射到 `start.py` 共享的启动契约上，
    # 这样两套脚本就能共用同一套环境准备逻辑。
    return argparse.Namespace(
        host=args.host,
        port=args.port,
        venv_dir=args.venv_dir,
        backend_only=False,
        force_python_install=args.force_python_install,
        force_node_install=args.force_node_install,
        force_frontend_build=args.force_frontend_build,
        enable_base_model_cache=args.enable_base_model_cache,
        online=args.online,
        allow_unsupported_python=args.allow_unsupported_python,
    )


def apply_production_defaults(args: argparse.Namespace) -> None:
    # 这里注入适合生产环境的默认值，但不会覆盖外部已经显式提供的环境变量。
    os.environ.setdefault('ENV', 'prod')
    os.environ.setdefault('DATA_DIR', args.data_dir)
    os.environ.setdefault('WEBUI_SECRET_KEY_FILE', args.secret_key_file)
    os.environ.setdefault('USER_AGENT', 'open-webui-start_prod.py')
    os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
    os.environ.setdefault('RAG_EMBEDDING_MODEL_AUTO_UPDATE', 'False')
    os.environ.setdefault('RAG_RERANKING_MODEL_AUTO_UPDATE', 'False')
    os.environ.setdefault('FORWARDED_ALLOW_IPS', args.forwarded_allow_ips)
    os.environ.setdefault('UVICORN_WORKERS', args.workers)
    os.environ.setdefault('UVICORN_WS', args.ws_mode)
    os.environ.setdefault('EMBEDDING_MODEL_DIR', str((ROOT / 'embedding_model').resolve()))
    os.environ.setdefault('SENTENCE_TRANSFORMERS_HOME', os.environ['EMBEDDING_MODEL_DIR'])
    os.environ.setdefault('HF_HOME', os.environ['EMBEDDING_MODEL_DIR'])
    os.environ.setdefault('NLTK_DATA', str((ROOT / 'nltk_data').resolve()))
    os.environ.setdefault('AUTO_DOWNLOAD_NLTK', 'False')
    os.environ.setdefault('ENABLE_UPLOAD_DECRYPTION', 'True')
    os.environ.setdefault('DECRYPT_SERVER_URL', '')
    os.environ.setdefault('DECRYPT_TIMEOUT_SECONDS', '120')
    os.environ.setdefault('DECRYPT_OUTPUT_DIR', str((ROOT / 'backend' / 'data' / 'uploads' / 'decrypted').resolve()))

    if not args.enable_base_model_cache:
        os.environ.setdefault('ENABLE_BASE_MODELS_CACHE', 'False')

    if args.online:
        os.environ.pop('OFFLINE_MODE', None)
        os.environ.pop('HF_HUB_OFFLINE', None)
        os.environ.pop('TRANSFORMERS_OFFLINE', None)
    else:
        os.environ.setdefault('OFFLINE_MODE', 'True')
        os.environ.setdefault('HF_HUB_OFFLINE', '1')
        os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
        os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')

    if args.offline:
        os.environ.setdefault('OFFLINE_MODE', 'True')

    if args.cors_origin:
        os.environ['CORS_ALLOW_ORIGIN'] = args.cors_origin
    elif 'CORS_ALLOW_ORIGIN' not in os.environ:
        log('未设置 CORS_ALLOW_ORIGIN。生产环境建议显式配置它。')


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_port_available(host: str, port: int) -> None:
    # 在真正启动前先探测端口，避免依赖装完之后才发现端口冲突。
    bind_targets = []

    if host in {'0.0.0.0', ''}:
        bind_targets.append(('0.0.0.0', socket.AF_INET))
    elif host == '::':
        bind_targets.append(('::', socket.AF_INET6))
    else:
        try:
            infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
        except socket.gaierror as exc:
            fail(f'无法解析主机地址 "{host}"：{exc}')

        for family, _, _, _, sockaddr in infos:
            bind_targets.append((sockaddr[0], family))

    checked_any = False
    for bind_host, family in bind_targets:
        checked_any = True
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            sock.bind((bind_host, port))
        except OSError as exc:
            fail(f'端口 {port} 在主机 "{host}" 上已被占用或不可用：{exc}')
        finally:
            sock.close()

    if not checked_any:
        fail(f'无法确认 {host}:{port} 是否可用。')


def timestamp() -> str:
    return datetime.now().strftime('%Y%m%d-%H%M%S')


def build_detached_log_paths(log_dir: Path) -> tuple[Path, Path]:
    stamp = timestamp()
    return (
        log_dir / f'open-webui-{stamp}.stdout.log',
        log_dir / f'open-webui-{stamp}.stderr.log',
    )


def exported_environment() -> dict[str, str]:
    # Windows 服务启动时不会继承当前终端的环境变量，
    # 因此这里把关键配置显式导出给服务包装器。
    env: dict[str, str] = {}
    explicit_keys = {
        'ENV',
        'DATA_DIR',
        'WEBUI_SECRET_KEY_FILE',
        'CORS_ALLOW_ORIGIN',
        'ENABLE_BASE_MODELS_CACHE',
        'RAG_EMBEDDING_MODEL_AUTO_UPDATE',
        'RAG_RERANKING_MODEL_AUTO_UPDATE',
        'OFFLINE_MODE',
        'HF_HUB_OFFLINE',
        'TRANSFORMERS_OFFLINE',
        'HF_HUB_DISABLE_TELEMETRY',
        'EMBEDDING_MODEL_DIR',
        'SENTENCE_TRANSFORMERS_HOME',
        'HF_HOME',
        'NLTK_DATA',
        'AUTO_DOWNLOAD_NLTK',
        'ENABLE_UPLOAD_DECRYPTION',
        'DECRYPT_SERVER_URL',
        'DECRYPT_TIMEOUT_SECONDS',
        'DECRYPT_OUTPUT_DIR',
        'FORWARDED_ALLOW_IPS',
        'UVICORN_WORKERS',
        'UVICORN_WS',
        'HF_HUB_DISABLE_SYMLINKS_WARNING',
        'USER_AGENT',
        'HTTP_PROXY',
        'HTTPS_PROXY',
        'ALL_PROXY',
        'NO_PROXY',
        'http_proxy',
        'https_proxy',
        'all_proxy',
        'no_proxy',
        'PIP_INDEX_URL',
        'PIP_EXTRA_INDEX_URL',
        'PIP_TRUSTED_HOST',
        'NPM_CONFIG_REGISTRY',
        'npm_config_registry',
    }

    prefix_groups = ('OPEN_WEBUI_', 'PIP_', 'NPM_CONFIG_', 'npm_config_')

    for key, value in os.environ.items():
        if not value:
            continue
        if key in explicit_keys or key.startswith(prefix_groups):
            env[key] = value

    return env


def build_child_command(args: argparse.Namespace, venv_python: Path) -> list[str]:
    # Windows 服务包装器最终会拉起这个命令，所以这里必须把关键参数完整带上。
    command = [
        str(venv_python),
        str(Path(__file__).resolve()),
        '--host',
        args.host,
        '--port',
        str(args.port),
        '--venv-dir',
        args.venv_dir,
        '--data-dir',
        args.data_dir,
        '--secret-key-file',
        args.secret_key_file,
        '--log-dir',
        args.log_dir,
        '--workers',
        args.workers,
        '--forwarded-allow-ips',
        args.forwarded_allow_ips,
        '--ws-mode',
        args.ws_mode,
    ]

    if args.cors_origin:
        command.extend(['--cors-origin', args.cors_origin])
    if args.enable_base_model_cache:
        command.append('--enable-base-model-cache')
    if args.offline:
        command.append('--offline')
    if args.online:
        command.append('--online')
    if args.allow_unsupported_python:
        command.append('--allow-unsupported-python')

    return command


def service_exists(service_name: str) -> bool:
    result = subprocess.run(
        ['sc.exe', 'query', service_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0


def write_service_config(args: argparse.Namespace, prepared: start.PreparedRuntime, log_dir: Path) -> None:
    ensure_directory(SERVICE_DIR)
    service_stdout = log_dir / 'service-stdout.log'
    service_stderr = log_dir / 'service-stderr.log'

    config = {
        'service_name': args.service_name,
        'service_display_name': args.service_display_name,
        'service_description': args.service_description,
        'cwd': str(ROOT),
        'command': build_child_command(args, prepared.venv_python),
        'env': exported_environment(),
        'stdout_log': str(service_stdout),
        'stderr_log': str(service_stderr),
    }
    SERVICE_CONFIG.write_text(json.dumps(config, indent=2), encoding='utf-8')


def run_service_command(venv_python: Path, command_args: list[str]) -> None:
    command = [str(venv_python), str(SERVICE_SCRIPT), *command_args]
    log(f'正在执行服务命令: {subprocess.list2cmdline(command)}')
    subprocess.run(command, cwd=str(ROOT), check=True)


def install_service(args: argparse.Namespace, prepared: start.PreparedRuntime, log_dir: Path) -> None:
    if service_exists(args.service_name):
        fail(
            f'服务 "{args.service_name}" 已存在。若要重建，请先执行 --remove-service。'
        )

    write_service_config(args, prepared, log_dir)
    run_service_command(
        prepared.venv_python,
        ['--startup', args.service_startup, 'install'],
    )
    if not service_exists(args.service_name):
        fail(
            f'服务 "{args.service_name}" 创建失败。通常意味着当前终端没有管理员权限。'
        )
    log(f'服务 "{args.service_name}" 安装成功。')


def remove_service(args: argparse.Namespace, venv_python: Path) -> None:
    if not service_exists(args.service_name):
        log(f'服务 "{args.service_name}" 不存在，无需卸载。')
        return

    run_service_command(venv_python, ['remove'])
    log(f'服务 "{args.service_name}" 已卸载。')


def start_service(args: argparse.Namespace, venv_python: Path) -> None:
    if not service_exists(args.service_name):
        fail(f'服务 "{args.service_name}" 不存在。')

    run_service_command(venv_python, ['start'])
    log(f'已请求启动服务 "{args.service_name}"。')


def stop_service(args: argparse.Namespace, venv_python: Path) -> None:
    if not service_exists(args.service_name):
        fail(f'服务 "{args.service_name}" 不存在。')

    run_service_command(venv_python, ['stop'])
    log(f'已请求停止服务 "{args.service_name}"。')


def detached_creationflags() -> int:
    if os.name != 'nt':
        return 0
    return subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS


def run_detached(args: argparse.Namespace, prepared: start.PreparedRuntime, log_dir: Path) -> None:
    ensure_port_available(args.host, args.port)

    stdout_log, stderr_log = build_detached_log_paths(log_dir)
    with stdout_log.open('a', encoding='utf-8') as stdout_handle, stderr_log.open(
        'a',
        encoding='utf-8',
    ) as stderr_handle:
        process = start.launch_open_webui(
            prepared,
            build_start_namespace(args),
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=detached_creationflags(),
            wait=False,
        )

    log(f'后台进程已启动，PID: {process.pid}')
    log(f'标准输出日志: {stdout_log}')
    log(f'标准错误日志: {stderr_log}')
    log(f'本机访问地址: {start.browser_url(args.host, args.port)}')
    for lan_ip in start.collect_lan_ipv4_addresses():
        log(f'局域网访问地址: http://{lan_ip}:{args.port}')


def prepare_and_optionally_run(args: argparse.Namespace, start_args: argparse.Namespace) -> None:
    log_dir = ensure_directory(Path(args.log_dir).resolve())
    prepared = start.prepare_runtime(start_args)

    if args.prepare_only:
        log('环境准备完成。由于传入了 --prepare-only，本次不会真正启动应用。')
        return

    if args.install_service:
        install_service(args, prepared, log_dir)
        if args.start_service:
            start_service(args, prepared.venv_python)
        return

    if args.detach:
        run_detached(args, prepared, log_dir)
        return

    ensure_port_available(args.host, args.port)
    start.launch_open_webui(prepared, start_args)


def main(argv: list[str] | None = None) -> None:
    os.chdir(ROOT)
    args = parse_args(argv)
    start_args = build_start_namespace(args)

    apply_production_defaults(args)

    start.maybe_reexec_with_supported_python(
        start_args,
        script_path=Path(__file__).resolve(),
        forwarded_args=argv if argv is not None else sys.argv[1:],
    )

    # Windows 服务相关命令与普通启动不同：
    # - install 需要先完成环境准备
    # - start/stop/remove 只需要能找到目标虚拟环境中的 Python
    venv_python = (ROOT / args.venv_dir / 'Scripts' / 'python.exe').resolve()

    if args.remove_service:
        if not venv_python.exists():
            fail(f'未找到虚拟环境解释器: {venv_python}')
        remove_service(args, venv_python)
        return

    if args.start_service and not args.install_service:
        if not venv_python.exists():
            fail(f'未找到虚拟环境解释器: {venv_python}')
        start_service(args, venv_python)
        return

    if args.stop_service:
        if not venv_python.exists():
            fail(f'未找到虚拟环境解释器: {venv_python}')
        stop_service(args, venv_python)
        return

    prepare_and_optionally_run(args, start_args)


def run_cli(argv: list[str] | None = None) -> None:
    try:
        main(argv)
    except KeyboardInterrupt:
        log('收到中断信号，正在停止服务...')
        raise SystemExit(130)


if __name__ == '__main__':
    run_cli()
