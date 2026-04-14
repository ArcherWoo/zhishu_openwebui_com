from __future__ import annotations

import io
import socket
import signal
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import prefetch_vendor_deps as prefetch_vendor_deps
import start
import start_prod
from open_webui import uvicorn_runner


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


def test_build_uvicorn_command_uses_wrapper_module_for_clean_interrupt_shutdown():
    args = SimpleNamespace(host='0.0.0.0', port=8080)
    venv_python = Path('C:/fake/python.exe')

    command = start.build_uvicorn_command(
        venv_python,
        args,
        {
            'FORWARDED_ALLOW_IPS': '*',
            'UVICORN_WORKERS': '1',
            'UVICORN_WS': 'auto',
        },
    )

    assert command[:3] == [str(venv_python), '-m', 'open_webui.uvicorn_runner']
    assert '--host' in command
    assert '--port' in command
    assert '--workers' in command
    assert '--ws' in command


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


def test_terminate_process_gracefully_uses_ctrl_break_for_windows_process_groups(monkeypatch):
    class DummyProcess:
        def __init__(self):
            self.returncode = None
            self.signals = []

        def send_signal(self, signal_value):
            self.signals.append(signal_value)

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

    process = DummyProcess()

    monkeypatch.setattr(start.os, 'name', 'nt')

    return_code = start.terminate_process_gracefully(
        process,
        service_label='Open WebUI',
        use_ctrl_break=True,
    )

    assert return_code == 0
    assert process.signals == [signal.CTRL_BREAK_EVENT]


def test_launch_open_webui_uses_new_process_group_on_windows(monkeypatch):
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
    popen_calls = {}

    monkeypatch.setattr(start.os, 'name', 'nt')
    monkeypatch.setattr(start, 'collect_lan_ipv4_addresses', lambda: [])
    monkeypatch.setattr(start, 'build_uvicorn_command', lambda *_args, **_kwargs: ['python', '-m', 'uvicorn'])
    monkeypatch.setattr(start, 'run_managed_process', lambda *args, **kwargs: 0)

    class DummyProcess:
        returncode = 0

    def fake_popen(*args, **kwargs):
        popen_calls['creationflags'] = kwargs.get('creationflags', 0)
        return DummyProcess()

    monkeypatch.setattr(start.subprocess, 'Popen', fake_popen)

    start.launch_open_webui(prepared, args)

    assert popen_calls['creationflags'] & start.subprocess.CREATE_NEW_PROCESS_GROUP


def test_uvicorn_runner_returns_130_on_keyboard_interrupt(monkeypatch):
    def fake_run(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(uvicorn_runner.uvicorn, 'run', fake_run)

    exit_code = uvicorn_runner.main(['--host', '127.0.0.1', '--port', '8080'])

    assert exit_code == 130


def test_build_python_install_commands_use_vendor_first_strategy():
    venv_python = Path('C:/fake/python.exe')
    vendor_dir = Path('C:/repo/vendor/python')
    requirements_file = Path('C:/repo/backend/requirements.txt')

    local_cmd, fallback_cmd = start.build_python_install_commands(
        venv_python,
        vendor_dir,
        requirements_file,
    )

    assert local_cmd[:4] == [str(venv_python), '-m', 'pip', 'install']
    assert '--no-index' in local_cmd
    assert '--find-links' in local_cmd
    assert str(vendor_dir) in local_cmd
    assert str(requirements_file) in local_cmd

    assert fallback_cmd[:4] == [str(venv_python), '-m', 'pip', 'install']
    assert '--no-index' not in fallback_cmd
    assert '--find-links' in fallback_cmd
    assert str(vendor_dir) in fallback_cmd
    assert str(requirements_file) in fallback_cmd


def test_build_npm_install_commands_use_vendor_cache_first_strategy():
    vendor_dir = Path('C:/repo/vendor/npm')

    local_cmd, fallback_cmd = start.build_npm_install_commands(
        'npm.cmd',
        vendor_dir,
    )

    assert local_cmd == [
        'npm.cmd',
        'ci',
        '--cache',
        str(vendor_dir),
        '--offline',
    ]
    assert fallback_cmd == [
        'npm.cmd',
        'ci',
        '--cache',
        str(vendor_dir),
        '--prefer-offline',
    ]


def test_parse_requirements_entries_skips_comments_and_blank_lines():
    with tempfile.TemporaryDirectory() as temp_dir:
        requirements = Path(temp_dir) / 'requirements.txt'
        requirements.write_text(
            '\n'.join(
                [
                    '',
                    '# comment',
                    'fastapi==0.1.0',
                    'aiohttp==3.0.0 # inline comment',
                    '   ',
                ]
            ),
            encoding='utf-8',
        )

        assert prefetch_vendor_deps.parse_requirements_entries(requirements) == [
            'fastapi==0.1.0',
            'aiohttp==3.0.0',
        ]


def test_collect_npm_package_specs_from_lockfile_skips_root_and_file_links():
    lock_data = {
        'packages': {
            '': {'name': 'demo', 'version': '1.0.0'},
            'node_modules/react': {'version': '18.3.1'},
            'node_modules/@scope/pkg': {'version': '2.0.0'},
            'node_modules/local-pkg': {'version': '1.0.0', 'resolved': 'file:../local-pkg'},
            'node_modules/a/node_modules/b': {'version': '3.1.4'},
        }
    }

    assert prefetch_vendor_deps.collect_npm_package_specs(lock_data) == [
        '@scope/pkg@2.0.0',
        'b@3.1.4',
        'react@18.3.1',
    ]


def test_build_python_download_and_probe_commands():
    requirement = 'fastapi==0.1.0'
    vendor_dir = Path('C:/repo/vendor/python')

    download_cmd = prefetch_vendor_deps.build_python_download_command(
        'python',
        requirement,
        vendor_dir,
    )
    probe_cmd = prefetch_vendor_deps.build_python_probe_command(
        'python',
        requirement,
    )

    assert download_cmd == [
        'python',
        '-m',
        'pip',
        'download',
        '--dest',
        str(vendor_dir),
        requirement,
    ]
    assert probe_cmd == [
        'python',
        '-m',
        'pip',
        'install',
        '--dry-run',
        '--ignore-installed',
        '--no-deps',
        requirement,
    ]


def test_build_npm_cache_add_commands_support_dry_run():
    vendor_dir = Path('C:/repo/vendor/npm')

    download_cmd = prefetch_vendor_deps.build_npm_cache_add_command(
        'npm.cmd',
        'react@18.3.1',
        vendor_dir,
        dry_run=False,
    )
    dry_run_cmd = prefetch_vendor_deps.build_npm_cache_add_command(
        'npm.cmd',
        'react@18.3.1',
        vendor_dir,
        dry_run=True,
    )

    assert download_cmd == [
        'npm.cmd',
        'cache',
        'add',
        'react@18.3.1',
        '--cache',
        str(vendor_dir),
    ]
    assert dry_run_cmd == [
        'npm.cmd',
        'cache',
        'add',
        'react@18.3.1',
        '--cache',
        str(vendor_dir),
        '--dry-run',
    ]


def test_write_reports_includes_manual_recovery_commands():
    report = {
        'generated_at': '2026-04-13T00:00:00+00:00',
        'mode': 'download',
        'python': {
            'vendor_dir': 'vendor/python',
            'direct_requirements_total': 1,
            'direct_successful': [],
            'direct_failures': [
                {
                    'requirement': 'fastapi==0.1.0',
                    'error': 'missing',
                    'suggested_command': 'python -m pip download --dest vendor/python "fastapi==0.1.0"',
                }
            ],
            'bundle_failures': [],
            'full_dependency_download_complete': False,
            'full_dependency_error': 'missing transitive',
            'offline_validation_complete': False,
            'offline_validation_error': 'missing transitive',
            'artifact_file_count': 0,
        },
        'npm': {
            'vendor_dir': 'vendor/npm',
            'attempted_total': 1,
            'successful': [],
            'failures': [
                {
                    'package': 'react@18.3.1',
                    'error': 'missing',
                    'suggested_command': 'npm cache add "react@18.3.1" --cache vendor/npm',
                }
            ],
            'offline_validation_complete': False,
            'offline_validation_error': 'missing cache',
            'artifact_file_count': 0,
        },
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        report_json = Path(temp_dir) / 'report.json'
        report_md = Path(temp_dir) / 'report.md'

        prefetch_vendor_deps.write_reports(report, report_json=report_json, report_md=report_md)

        markdown = report_md.read_text(encoding='utf-8')
        assert '手工补包命令' in markdown
        assert 'python -m pip download --dest vendor/python "fastapi==0.1.0"' in markdown
        assert 'npm cache add "react@18.3.1" --cache vendor/npm' in markdown


def test_prefetch_parse_args_supports_verbose_flag():
    args = prefetch_vendor_deps.parse_args(['--dry-run', '--verbose'])

    assert args.dry_run is True
    assert args.verbose is True


def test_run_tracked_command_logs_progress_and_heartbeat(monkeypatch, capsys):
    class FakeProcess:
        def __init__(self):
            self.stdout = io.StringIO('')
            self.returncode = None
            self._poll_values = iter([None, None, 0])

        def poll(self):
            value = next(self._poll_values)
            if value is not None:
                self.returncode = value
            return value

        def wait(self):
            return self.returncode

    monkeypatch.setattr(
        prefetch_vendor_deps.subprocess,
        'Popen',
        lambda *args, **kwargs: FakeProcess(),
    )

    clock_ticks = iter([0.0, 11.0, 22.0, 33.0])
    monkeypatch.setattr(prefetch_vendor_deps.time, 'monotonic', lambda: next(clock_ticks))
    monkeypatch.setattr(prefetch_vendor_deps.time, 'sleep', lambda _seconds: None)

    result = prefetch_vendor_deps.run_tracked_command(
        ['python', '-m', 'pip', 'download', 'fastapi'],
        env={},
        phase='Python direct probe',
        item_label='fastapi==0.1.0',
        index=1,
        total=3,
        verbose=False,
        heartbeat_seconds=10.0,
    )

    assert result.returncode == 0
    captured = capsys.readouterr()
    assert 'Python direct probe [1/3] fastapi==0.1.0' in captured.out
    assert 'still running' in captured.out
    assert 'completed in' in captured.out


def test_run_tracked_command_streams_child_output_in_verbose_mode(monkeypatch, capsys):
    class FakeProcess:
        def __init__(self):
            self.stdout = io.StringIO('Collecting fastapi\nDownloading wheel\n')
            self.returncode = None
            self._poll_values = iter([0])

        def poll(self):
            value = next(self._poll_values)
            self.returncode = value
            return value

        def wait(self):
            return self.returncode

    monkeypatch.setattr(
        prefetch_vendor_deps.subprocess,
        'Popen',
        lambda *args, **kwargs: FakeProcess(),
    )
    monkeypatch.setattr(prefetch_vendor_deps.time, 'monotonic', lambda: 0.0)
    monkeypatch.setattr(prefetch_vendor_deps.time, 'sleep', lambda _seconds: None)

    result = prefetch_vendor_deps.run_tracked_command(
        ['python', '-m', 'pip', 'download', 'fastapi'],
        env={},
        phase='Python bundle download',
        item_label='fastapi==0.1.0',
        index=2,
        total=4,
        verbose=True,
        heartbeat_seconds=10.0,
    )

    assert result.returncode == 0
    captured = capsys.readouterr()
    assert 'Collecting fastapi' in captured.out
    assert 'Downloading wheel' in captured.out
