from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / 'backend'
RUNTIME_TEMP_DIR = ROOT / 'tmp-runtime-temp'

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def pytest_configure(config):
    RUNTIME_TEMP_DIR.mkdir(exist_ok=True)
    os.environ['TMP'] = str(RUNTIME_TEMP_DIR.resolve())
    os.environ['TEMP'] = str(RUNTIME_TEMP_DIR.resolve())
    os.environ['TMPDIR'] = str(RUNTIME_TEMP_DIR.resolve())
    tempfile.tempdir = str(RUNTIME_TEMP_DIR.resolve())
