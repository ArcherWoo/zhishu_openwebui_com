from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import servicemanager
import win32event
import win32service
import win32serviceutil


"""
Windows service wrapper for Open WebUI.

This file is not meant to be run directly by end users.
`start_prod.py --install-service` writes a JSON config file, then installs
this service using the production virtual environment's Python interpreter.
"""


ROOT = Path(__file__).resolve().parent
SERVICE_CONFIG = ROOT / 'service' / 'open_webui-service.json'


def load_service_config() -> dict:
    if not SERVICE_CONFIG.exists():
        return {
            'service_name': 'OpenWebUI',
            'service_display_name': 'Open WebUI',
            'service_description': 'Open WebUI production service',
            'cwd': str(ROOT),
            'command': [],
            'env': {},
            'stdout_log': str(ROOT / 'logs' / 'service-stdout.log'),
            'stderr_log': str(ROOT / 'logs' / 'service-stderr.log'),
        }

    return json.loads(SERVICE_CONFIG.read_text(encoding='utf-8'))


SERVICE_METADATA = load_service_config()


class OpenWebUIService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_METADATA['service_name']
    _svc_display_name_ = SERVICE_METADATA['service_display_name']
    _svc_description_ = SERVICE_METADATA['service_description']

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process: subprocess.Popen | None = None
        self.stdout_handle = None
        self.stderr_handle = None

    def log_info(self, message: str) -> None:
        servicemanager.LogInfoMsg(f'{self._svc_name_}: {message}')

    def log_error(self, message: str) -> None:
        servicemanager.LogErrorMsg(f'{self._svc_name_}: {message}')

    def terminate_child(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return

        self.process.terminate()
        try:
            self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.log_info('Stop requested.')
        self.terminate_child()
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        config = load_service_config()
        command = config.get('command', [])
        if not command:
            self.log_error('Service config does not contain a launch command.')
            return

        stdout_log = Path(config['stdout_log'])
        stderr_log = Path(config['stderr_log'])
        stdout_log.parent.mkdir(parents=True, exist_ok=True)
        stderr_log.parent.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env.update(config.get('env', {}))

        self.stdout_handle = stdout_log.open('a', encoding='utf-8')
        self.stderr_handle = stderr_log.open('a', encoding='utf-8')

        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        self.process = subprocess.Popen(
            command,
            cwd=config.get('cwd', str(ROOT)),
            env=env,
            stdout=self.stdout_handle,
            stderr=self.stderr_handle,
            creationflags=creationflags,
        )
        self.log_info(f'Child process started with PID {self.process.pid}.')
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)

        while True:
            wait_result = win32event.WaitForSingleObject(self.stop_event, 1000)
            if wait_result == win32event.WAIT_OBJECT_0:
                break

            if self.process.poll() is not None:
                self.log_error(f'Child process exited unexpectedly with code {self.process.returncode}.')
                break

        self.terminate_child()

        if self.stdout_handle:
            self.stdout_handle.close()
        if self.stderr_handle:
            self.stderr_handle.close()

        self.ReportServiceStatus(win32service.SERVICE_STOPPED)


if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(OpenWebUIService)
