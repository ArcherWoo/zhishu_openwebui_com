from __future__ import annotations

import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

import start
import start_prod


def test_run_cli_exits_cleanly_on_keyboard_interrupt(monkeypatch, capsys):
    def fake_main(argv=None):
        raise KeyboardInterrupt

    monkeypatch.setattr(start, 'main', fake_main)

    with pytest.raises(SystemExit) as exc_info:
        start.run_cli([])

    assert exc_info.value.code == 130
    captured = capsys.readouterr()
    assert '[start] 收到中断信号，正在停止服务...' in captured.out


def test_start_prod_run_cli_exits_cleanly_on_keyboard_interrupt(monkeypatch, capsys):
    def fake_main(argv=None):
        raise KeyboardInterrupt

    monkeypatch.setattr(start_prod, 'main', fake_main)

    with pytest.raises(SystemExit) as exc_info:
        start_prod.run_cli([])

    assert exc_info.value.code == 130
    captured = capsys.readouterr()
    assert '[start_prod] 收到中断信号，正在停止服务...' in captured.out


def test_browser_url_prefers_localhost_for_wildcard_host():
    assert start.browser_url('0.0.0.0', 8080) == 'http://localhost:8080'


def test_collect_lan_ipv4_addresses_prefers_private_ipv4_addresses(monkeypatch):
    addresses = [
        (socket.AF_INET, None, None, None, ('127.0.0.1', 0)),
        (socket.AF_INET, None, None, None, ('8.8.8.8', 0)),
        (socket.AF_INET, None, None, None, ('192.168.1.20', 0)),
        (socket.AF_INET, None, None, None, ('172.20.5.9', 0)),
        (socket.AF_INET, None, None, None, ('10.0.0.8', 0)),
        (socket.AF_INET, None, None, None, ('192.168.1.20', 0)),
        (socket.AF_INET6, None, None, None, ('fe80::1', 0, 0, 0)),
    ]

    monkeypatch.setattr(start.socket, 'gethostname', lambda: 'open-webui-host')
    monkeypatch.setattr(start.socket, 'getaddrinfo', lambda *args, **kwargs: addresses)

    assert start.collect_lan_ipv4_addresses() == ['192.168.1.20', '172.20.5.9', '10.0.0.8']


def test_launch_open_webui_logs_browser_and_lan_urls(monkeypatch, capsys):
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

    monkeypatch.setattr(start, 'build_uvicorn_command', lambda *_args, **_kwargs: ['python', '-m', 'uvicorn'])
    monkeypatch.setattr(start, 'collect_lan_ipv4_addresses', lambda: ['192.168.1.20'])

    class DummyProcess:
        returncode = 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(start.subprocess, 'Popen', lambda *args, **kwargs: DummyProcess())

    start.launch_open_webui(prepared, args)

    captured = capsys.readouterr()
    assert '[start] Open WebUI 已启动。' in captured.out
    assert '[start] 本机访问地址: http://localhost:8080' in captured.out
    assert '[start] 局域网访问地址: http://192.168.1.20:8080' in captured.out


def test_run_managed_process_logs_graceful_shutdown_and_returns_130(capsys):
    class DummyProcess:
        def __init__(self):
            self.returncode = None
            self.terminated = False

        def wait(self, timeout=None):
            if not self.terminated:
                raise KeyboardInterrupt
            self.returncode = 0
            return 0

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.terminated = True

    process = DummyProcess()

    with pytest.raises(SystemExit) as exc_info:
        start.run_managed_process(process, service_label='Open WebUI')

    assert exc_info.value.code == 130
    captured = capsys.readouterr()
    assert '[start] 收到中断信号，正在优雅关闭 Open WebUI...' in captured.out
    assert '[start] Open WebUI 已停止。' in captured.out
