from __future__ import annotations

import io
import shutil
import sys
from itertools import count
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / 'backend'
TEMP_ROOT = ROOT / 'tmp-test-artifacts'
TEMP_COUNTER = count()

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from open_webui.routers import files as files_router
from open_webui.utils.decrypt import DecryptError, validate_decrypt_result


class DummyUploadFile:
    def __init__(
        self,
        filename: str = 'cipher.txt',
        content_type: str = 'text/plain',
        body: bytes = b'cipher',
    ):
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(body)


def build_request():
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    ALLOWED_FILE_EXTENSIONS=[],
                )
            )
        )
    )


def build_user():
    return SimpleNamespace(id='user-1', email='u@example.com', name='User')


@pytest.fixture
def temp_dir():
    TEMP_ROOT.mkdir(exist_ok=True)
    path = TEMP_ROOT / f'upload-decryption-{next(TEMP_COUNTER)}'
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_validate_decrypt_result_accepts_existing_output(temp_dir):
    output_path = temp_dir / 'plain.txt'
    output_path.write_text('hello', encoding='utf-8')

    result = validate_decrypt_result(
        {
            'success': True,
            'output_path': str(output_path),
            'filename': 'plain.txt',
            'content_type': 'text/plain',
            'message': 'ok',
        },
        original_filename='cipher.txt',
        original_content_type='application/octet-stream',
    )

    assert result.output_path == output_path
    assert result.filename == 'plain.txt'
    assert result.size == len(output_path.read_bytes())


def test_validate_decrypt_result_rejects_missing_output_file(temp_dir):
    missing = temp_dir / 'missing.txt'

    with pytest.raises(DecryptError, match='输出文件不存在'):
        validate_decrypt_result(
            {'success': True, 'output_path': str(missing)},
            original_filename='cipher.txt',
            original_content_type=None,
        )


def test_upload_file_handler_uses_decrypted_output(monkeypatch, temp_dir):
    encrypted_path = temp_dir / 'encrypted.txt'
    decrypted_path = temp_dir / 'decrypted.txt'
    stored_path = temp_dir / 'stored.txt'
    encrypted_path.write_bytes(b'cipher')
    decrypted_path.write_text('plain', encoding='utf-8')
    decrypted_size = len(decrypted_path.read_bytes())

    inserted: dict[str, object] = {}
    upload_calls: list[bytes] = []

    def fake_upload_file(file_obj, _filename, _tags):
        data = file_obj.read()
        upload_calls.append(data)
        if len(upload_calls) == 1:
            encrypted_path.write_bytes(data)
            return data, str(encrypted_path)

        stored_path.write_bytes(data)
        return data, str(stored_path)

    monkeypatch.setattr(files_router.Storage, 'upload_file', fake_upload_file)
    monkeypatch.setattr(files_router.Storage, 'get_file', lambda file_path: file_path)
    monkeypatch.setattr(
        files_router,
        'decrypt_uploaded_file',
        lambda **_kwargs: SimpleNamespace(
            output_path=decrypted_path,
            filename='plain.txt',
            content_type='text/plain',
            size=len(decrypted_path.read_bytes()),
            message='ok',
        ),
        raising=False,
    )

    def fake_insert_new_file(user_id, form_data, db=None):
        inserted['user_id'] = user_id
        inserted['form'] = form_data
        return SimpleNamespace(
            id=form_data.id,
            model_dump=lambda: {'id': form_data.id},
        )

    monkeypatch.setattr(files_router.Files, 'insert_new_file', fake_insert_new_file)
    monkeypatch.setattr(files_router, 'process_uploaded_file', lambda *args, **kwargs: None)

    files_router.upload_file_handler(
        build_request(),
        file=DummyUploadFile(),
        metadata=None,
        process=False,
        user=build_user(),
        background_tasks=None,
        db=None,
    )

    form = inserted['form']
    assert form.path == str(stored_path)
    assert form.filename == 'plain.txt'
    assert form.meta['name'] == 'plain.txt'
    assert form.meta['size'] == decrypted_size
    assert form.meta['content_type'] == 'text/plain'
    assert upload_calls == [b'cipher', b'plain']
    assert stored_path.read_text(encoding='utf-8') == 'plain'


def test_upload_file_handler_raises_http_400_when_decrypt_fails(monkeypatch, temp_dir):
    encrypted_path = temp_dir / 'encrypted.txt'
    encrypted_path.write_bytes(b'cipher')

    monkeypatch.setattr(
        files_router.Storage,
        'upload_file',
        lambda *_args, **_kwargs: (b'cipher', str(encrypted_path)),
    )
    monkeypatch.setattr(files_router.Storage, 'get_file', lambda file_path: file_path)
    monkeypatch.setattr(files_router.Storage, 'delete_file', lambda _file_path: None)

    def fake_decrypt(**_kwargs):
        raise DecryptError('解密服务返回失败')

    monkeypatch.setattr(files_router, 'decrypt_uploaded_file', fake_decrypt, raising=False)

    with pytest.raises(HTTPException) as exc_info:
        files_router.upload_file_handler(
            build_request(),
            file=DummyUploadFile(),
            metadata=None,
            process=False,
            user=build_user(),
            background_tasks=None,
            db=None,
        )

    assert exc_info.value.status_code == 400
    assert '文件解密失败' in exc_info.value.detail
