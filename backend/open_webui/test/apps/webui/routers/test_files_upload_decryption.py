import io
from pathlib import Path
from types import SimpleNamespace

from open_webui.routers import files as files_router
from open_webui.utils.decrypt import DecryptResult


class DummyStorage:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.upload_calls = []

    def upload_file(self, file, filename, tags):
        content = file.read()
        path = self.root / filename
        path.write_bytes(content)
        self.upload_calls.append(
            {
                "filename": filename,
                "path": str(path),
                "content": content,
                "tags": tags,
            }
        )
        return content, str(path)

    def get_file(self, file_path):
        return file_path

    def delete_file(self, file_path):
        path = Path(file_path)
        if path.exists():
            path.unlink()


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
    return SimpleNamespace(
        id="user-1",
        email="user@example.com",
        name="Test User",
    )


def build_file(filename: str, content_type: str, content: bytes):
    return SimpleNamespace(
        filename=filename,
        content_type=content_type,
        file=io.BytesIO(content),
    )


def test_upload_file_handler_uploads_only_decrypted_file_once(monkeypatch, tmp_path):
    storage = DummyStorage(tmp_path / "storage")
    decrypted_path = tmp_path / "decrypted" / "deck.pptx"
    decrypted_path.parent.mkdir(parents=True, exist_ok=True)
    decrypted_path.write_bytes(b"decrypted-pptx")

    request = build_request()
    user = build_user()
    upload = build_file("deck.enc", "application/octet-stream", b"encrypted-ppt")
    captured = {}

    def fake_decrypt_uploaded_file(input_path, original_filename, content_type, metadata=None, config=None):
        assert Path(input_path).is_file()
        return DecryptResult(
            output_path=decrypted_path,
            filename="deck.pptx",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            size=decrypted_path.stat().st_size,
            message="ok",
        )

    def fake_insert_new_file(user_id, form_data, db=None):
        captured["user_id"] = user_id
        captured["form_data"] = form_data
        return SimpleNamespace(
            id=form_data.id,
            filename=form_data.filename,
            model_dump=lambda: {
                "id": form_data.id,
                "filename": form_data.filename,
                "meta": form_data.meta,
            },
        )

    monkeypatch.setattr(files_router, "Storage", storage)
    monkeypatch.setattr(files_router, "decrypt_uploaded_file", fake_decrypt_uploaded_file)
    monkeypatch.setattr(files_router.Files, "insert_new_file", fake_insert_new_file)

    files_router.upload_file_handler(
        request=request,
        file=upload,
        metadata=None,
        process=False,
        process_in_background=False,
        user=user,
        background_tasks=None,
        db=None,
    )

    assert len(storage.upload_calls) == 1
    assert storage.upload_calls[0]["filename"].endswith("_deck.pptx")
    assert captured["form_data"].filename == "deck.pptx"
    assert captured["form_data"].path == storage.upload_calls[0]["path"]
    assert (
        captured["form_data"].meta["content_type"]
        == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )


def test_upload_file_handler_processes_decrypted_storage_path(monkeypatch, tmp_path):
    storage = DummyStorage(tmp_path / "storage")
    decrypted_path = tmp_path / "decrypted" / "deck.pptx"
    decrypted_path.parent.mkdir(parents=True, exist_ok=True)
    decrypted_path.write_bytes(b"decrypted-pptx")

    request = build_request()
    user = build_user()
    upload = build_file("deck.enc", "application/octet-stream", b"encrypted-ppt")
    processed = {}

    def fake_decrypt_uploaded_file(input_path, original_filename, content_type, metadata=None, config=None):
        return DecryptResult(
            output_path=decrypted_path,
            filename="deck.pptx",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            size=decrypted_path.stat().st_size,
            message="ok",
        )

    def fake_insert_new_file(user_id, form_data, db=None):
        return SimpleNamespace(
            id=form_data.id,
            filename=form_data.filename,
            model_dump=lambda: {
                "id": form_data.id,
                "filename": form_data.filename,
                "meta": form_data.meta,
            },
        )

    def fake_process_uploaded_file(request, file, file_path, file_item, file_metadata, user, db=None):
        processed["file_path"] = file_path
        processed["content_type"] = file.content_type

    monkeypatch.setattr(files_router, "Storage", storage)
    monkeypatch.setattr(files_router, "decrypt_uploaded_file", fake_decrypt_uploaded_file)
    monkeypatch.setattr(files_router.Files, "insert_new_file", fake_insert_new_file)
    monkeypatch.setattr(files_router, "process_uploaded_file", fake_process_uploaded_file)

    files_router.upload_file_handler(
        request=request,
        file=upload,
        metadata=None,
        process=True,
        process_in_background=False,
        user=user,
        background_tasks=None,
        db=None,
    )

    assert processed["file_path"].endswith("_deck.pptx")
    assert (
        processed["content_type"]
        == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
