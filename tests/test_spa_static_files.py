from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from open_webui.utils.static_files import SPAStaticFiles

TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / 'tmp-test-artifacts' / 'spa-static-files'


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def _make_temp_dir() -> Path:
    path = TEST_TEMP_ROOT / str(uuid.uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_spa_index_html_is_not_cached():
    tmp_path = _make_temp_dir()
    try:
        _write(tmp_path / 'index.html', '<!doctype html><title>spa</title>')
        _write(tmp_path / '_app' / 'immutable' / 'entry.js', 'console.log("ok")')

        app = FastAPI()
        app.mount('/', SPAStaticFiles(directory=tmp_path, html=True), name='spa')
        client = TestClient(app)

        response = client.get('/notes/example-id')

        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store, max-age=0'
        assert response.headers['Pragma'] == 'no-cache'
        assert response.headers['Expires'] == '0'
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_spa_missing_javascript_still_returns_404():
    tmp_path = _make_temp_dir()
    try:
        _write(tmp_path / 'index.html', '<!doctype html><title>spa</title>')

        app = FastAPI()
        app.mount('/', SPAStaticFiles(directory=tmp_path, html=True), name='spa')
        client = TestClient(app)

        response = client.get('/_app/immutable/nodes/missing.js')

        assert response.status_code == 404
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
