from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding='utf-8')


def test_package_json_no_longer_forces_pyodide_fetch_for_build_or_dev():
    package_json = json.loads(read_text('package.json'))
    scripts = package_json['scripts']

    assert 'pyodide:fetch' not in scripts['dev']
    assert 'pyodide:fetch' not in scripts['dev:5050']
    assert 'pyodide:fetch' not in scripts['build']
    assert 'pyodide:fetch' not in scripts['build:watch']


def test_package_json_no_longer_requires_pyodide_npm_dependency():
    package_json = json.loads(read_text('package.json'))

    assert 'pyodide' not in package_json['dependencies']


def test_prepare_pyodide_script_uses_optional_runtime_loading():
    script = read_text('scripts/prepare-pyodide.js')

    assert "from 'pyodide'" not in script
    assert 'OPEN_WEBUI_ALLOW_PYODIDE_DOWNLOAD' in script


def test_pyodide_workers_load_browser_runtime_from_static_assets():
    worker_paths = [
        'src/lib/workers/pyodide.worker.ts',
        'src/lib/pyodide/pyodideKernel.worker.ts',
    ]

    for worker_path in worker_paths:
        content = read_text(worker_path)
        assert "from 'pyodide'" not in content
        assert '/pyodide/pyodide.mjs' in content
        assert '@vite-ignore' in content


def test_code_execution_defaults_are_disabled():
    config_source = read_text('backend/open_webui/config.py')

    assert "os.environ.get('ENABLE_CODE_EXECUTION', 'False').lower() == 'true'" in config_source
    assert "os.environ.get('ENABLE_CODE_INTERPRETER', 'False').lower() == 'true'" in config_source


def test_code_block_run_button_defaults_to_disabled_until_config_is_loaded():
    code_block = read_text('src/lib/components/chat/Messages/CodeBlock.svelte')

    assert 'enable_code_execution ?? false' in code_block
