from __future__ import annotations

import io
import shutil
import sys
from itertools import count
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / 'backend'
TEMP_ROOT = ROOT / 'tmp-test-artifacts'
TEMP_COUNTER = count()

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from open_webui.routers import files as files_router


class DummyUploadFile:
    def __init__(
        self,
        filename: str = 'generated.txt',
        content_type: str = 'text/plain',
        body: bytes = b'plain text',
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


def make_temp_dir() -> Path:
    TEMP_ROOT.mkdir(exist_ok=True)
    path = TEMP_ROOT / f'generated-upload-{next(TEMP_COUNTER)}'
    path.mkdir()
    return path


def test_generated_text_upload_skips_decryption():
    temp_dir = make_temp_dir()
    stored_path = temp_dir / 'stored.txt'
    inserted: dict[str, object] = {}

    try:
        files_router.Storage.upload_file = lambda file_obj, _filename, _tags: (file_obj.read(), str(stored_path))
        files_router.Storage.get_file = lambda file_path: file_path

        def fail_if_called(**_kwargs):
            raise AssertionError('decrypt_uploaded_file should not be called for generated text content')

        original_decrypt = files_router.decrypt_uploaded_file
        original_insert = files_router.Files.insert_new_file
        files_router.decrypt_uploaded_file = fail_if_called

        def fake_insert_new_file(user_id, form_data, db=None):
            inserted['user_id'] = user_id
            inserted['form'] = form_data
            return SimpleNamespace(
                id=form_data.id,
                model_dump=lambda: {'id': form_data.id},
            )

        files_router.Files.insert_new_file = fake_insert_new_file

        result = files_router.upload_file_handler(
            build_request(),
            file=DummyUploadFile(),
            metadata={'knowledge_id': 'kb-1', 'skip_decryption': True},
            process=False,
            user=build_user(),
            background_tasks=None,
            db=None,
        )

        form = inserted['form']
        assert result.id == form.id
        assert form.path == str(stored_path)
        assert form.filename == 'generated.txt'
        assert form.meta['name'] == 'generated.txt'
        assert form.meta['content_type'] == 'text/plain'
        assert form.meta['size'] == len(b'plain text')
        assert form.meta['data'] == {'knowledge_id': 'kb-1'}
    finally:
        files_router.decrypt_uploaded_file = original_decrypt
        files_router.Files.insert_new_file = original_insert
        shutil.rmtree(temp_dir, ignore_errors=True)
