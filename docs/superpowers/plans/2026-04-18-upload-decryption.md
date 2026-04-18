# 文件上传自动解密实施计划

> **给执行型 agent 的说明：** 实施本计划时，必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，并按任务逐项执行。步骤使用复选框 `- [ ]` 跟踪。

**目标：** 让所有通过 `/api/v1/files/` 上传的文件，在进入解析和知识库入库之前必须先解密；如果解密失败，则上传直接失败。

**架构：** 企业内网的解密细节全部收口到一个统一适配层。后端上传路由继续负责原有上传主流程，但在中间调用新的 `backend/open_webui/utils/decrypt.py`；这个适配层再去加载根目录固定入口 `decrypt/client.py`。启动脚本负责提供默认环境变量，测试则通过 monkeypatch 隔离存储和解密逻辑。

**技术栈：** Python、FastAPI 路由、pytest、Open WebUI 现有 files/storage/config 结构、Markdown 文档。

---

## 文件地图

- 新建：`tests/test_upload_decryption.py`
  - 覆盖上传自动解密的路由级测试，包括解密成功、解密失败、返回值非法、启动默认配置等。
- 新建：`backend/open_webui/utils/decrypt.py`
  - 统一解密适配层，负责读取配置、加载 `decrypt.client`、执行解密、校验结果，并暴露 `decrypt_uploaded_file()`。
- 新建：`decrypt/__init__.py`
  - 让根目录 `decrypt/` 可以被 Python 正常导入。
- 新建：`decrypt/client.py`
  - 固定接口骨架，要求后续由你填入公司解密服务调用逻辑。
- 新建：`decrypt/README.md`
  - 中文接入说明，告诉你怎样把公司内网的亿赛通解密逻辑接进来。
- 修改：`backend/open_webui/routers/files.py`
  - 在上传主流程里接入解密，成功后改用解密后的文件，失败时中断上传，并清理中间文件。
- 修改：`backend/open_webui/config.py`
  - 增加解密相关配置项，供运行时通过 `request.app.state.config` 读取。
- 修改：`start.py`
  - 为解密相关环境变量提供默认值。
- 修改：`start_prod.py`
  - 为生产启动和 Windows 服务模式导出解密相关环境变量。
- 修改：`service/open_webui-service.json`
  - 增加示例性的解密环境变量占位。

## 任务 1：先补失败测试，锁定目标行为

**文件：**
- 新建：`tests/test_upload_decryption.py`
- 测试：`tests/test_upload_decryption.py`

- [ ] **步骤 1：先写解密结果校验的失败测试**

```python
from pathlib import Path

import pytest

from backend.open_webui.utils.decrypt import DecryptError, validate_decrypt_result


def test_validate_decrypt_result_accepts_existing_output(tmp_path):
    output_path = tmp_path / "plain.txt"
    output_path.write_text("hello", encoding="utf-8")

    result = validate_decrypt_result(
        {
            "success": True,
            "output_path": str(output_path),
            "filename": "plain.txt",
            "content_type": "text/plain",
            "message": "ok",
        },
        original_filename="cipher.txt",
        original_content_type="application/octet-stream",
    )

    assert result.output_path == output_path
    assert result.filename == "plain.txt"
    assert result.size == len(output_path.read_bytes())


def test_validate_decrypt_result_rejects_missing_output_file(tmp_path):
    missing = tmp_path / "missing.txt"

    with pytest.raises(DecryptError, match="输出文件不存在"):
        validate_decrypt_result(
            {"success": True, "output_path": str(missing)},
            original_filename="cipher.txt",
            original_content_type=None,
        )
```

- [ ] **步骤 2：运行测试，确认当前一定失败**

运行：

```bash
pytest tests/test_upload_decryption.py -k validate_decrypt_result -q
```

预期：

- 因为 `backend/open_webui/utils/decrypt.py` 还不存在，所以会先报 import 错误。

- [ ] **步骤 3：补上传主流程的失败测试**

```python
import io
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from open_webui.routers import files as files_router


class DummyUploadFile:
    def __init__(self, filename="cipher.txt", content_type="text/plain", body=b"cipher"):
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(body)


def test_upload_file_handler_uses_decrypted_output(monkeypatch, tmp_path):
    encrypted_path = tmp_path / "encrypted.txt"
    decrypted_path = tmp_path / "decrypted.txt"
    encrypted_path.write_bytes(b"cipher")
    decrypted_path.write_text("plain", encoding="utf-8")

    inserted = {}

    monkeypatch.setattr(
        files_router.Storage,
        "upload_file",
        lambda *_args, **_kwargs: (b"cipher", str(encrypted_path)),
    )
    monkeypatch.setattr(
        files_router,
        "decrypt_uploaded_file",
        lambda **_kwargs: SimpleNamespace(
            output_path=decrypted_path,
            filename="plain.txt",
            content_type="text/plain",
            size=len(decrypted_path.read_bytes()),
            message="ok",
        ),
    )
    monkeypatch.setattr(
        files_router.Files,
        "insert_new_file",
        lambda user_id, form_data, db=None: inserted.setdefault("form", form_data) or SimpleNamespace(
            id=form_data.id,
            model_dump=lambda: {"id": form_data.id},
        ),
    )
    monkeypatch.setattr(files_router, "process_uploaded_file", lambda *args, **kwargs: None)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(config=SimpleNamespace(ALLOWED_FILE_EXTENSIONS=[]))))
    user = SimpleNamespace(id="user-1", email="u@example.com", name="User")

    files_router.upload_file_handler(
        request,
        file=DummyUploadFile(),
        metadata=None,
        process=False,
        user=user,
        background_tasks=None,
        db=None,
    )

    assert inserted["form"].path == str(decrypted_path)
    assert inserted["form"].meta["name"] == "plain.txt"
    assert inserted["form"].meta["size"] == len(decrypted_path.read_bytes())


def test_upload_file_handler_raises_http_400_when_decrypt_fails(monkeypatch, tmp_path):
    encrypted_path = tmp_path / "encrypted.txt"
    encrypted_path.write_bytes(b"cipher")

    monkeypatch.setattr(
        files_router.Storage,
        "upload_file",
        lambda *_args, **_kwargs: (b"cipher", str(encrypted_path)),
    )
    monkeypatch.setattr(
        files_router,
        "decrypt_uploaded_file",
        lambda **_kwargs: (_ for _ in ()).throw(files_router.HTTPException(status_code=400, detail="文件解密失败")),
    )

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(config=SimpleNamespace(ALLOWED_FILE_EXTENSIONS=[]))))
    user = SimpleNamespace(id="user-1", email="u@example.com", name="User")

    with pytest.raises(HTTPException, match="文件解密失败"):
        files_router.upload_file_handler(
            request,
            file=DummyUploadFile(),
            metadata=None,
            process=False,
            user=user,
            background_tasks=None,
            db=None,
        )
```

- [ ] **步骤 4：运行上传路由测试，确认它们现在失败**

运行：

```bash
pytest tests/test_upload_decryption.py -k upload_file_handler -q
```

预期：

- 失败，因为 `files.py` 里现在还没有真正接入 `decrypt_uploaded_file()`。

- [ ] **步骤 5：提交这一批红灯测试**

```bash
git add tests/test_upload_decryption.py
git commit -m "test: add upload decryption coverage"
```

## 任务 2：实现统一解密适配层和根目录固定接口

**文件：**
- 新建：`backend/open_webui/utils/decrypt.py`
- 新建：`decrypt/__init__.py`
- 新建：`decrypt/client.py`
- 测试：`tests/test_upload_decryption.py`

- [ ] **步骤 1：先写最小可用的解密适配层**

```python
from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DecryptError(RuntimeError):
    pass


@dataclass(slots=True)
class DecryptResult:
    output_path: Path
    filename: str
    content_type: str | None
    size: int
    message: str | None = None


@dataclass(slots=True)
class DecryptConfig:
    enabled: bool
    server_url: str
    timeout_seconds: int
    output_dir: Path


def validate_decrypt_result(payload: dict[str, Any], original_filename: str, original_content_type: str | None) -> DecryptResult:
    if not payload.get("success"):
        raise DecryptError(payload.get("message") or "文件解密失败")

    output_path_value = payload.get("output_path")
    if not output_path_value:
        raise DecryptError("解密结果缺少 output_path")

    output_path = Path(output_path_value)
    if not output_path.is_file():
        raise DecryptError("解密结果输出文件不存在")

    filename = payload.get("filename") or output_path.name or original_filename
    content_type = payload.get("content_type") or original_content_type

    return DecryptResult(
        output_path=output_path,
        filename=filename,
        content_type=content_type,
        size=output_path.stat().st_size,
        message=payload.get("message"),
    )


def load_client_module():
    return importlib.import_module("decrypt.client")
```

- [ ] **步骤 2：补齐配置读取和上传入口统一调用方法**

```python
def load_decrypt_config() -> DecryptConfig:
    root = Path(__file__).resolve().parents[3]
    output_dir = Path(os.environ.get("DECRYPT_OUTPUT_DIR", root / "backend" / "data" / "uploads" / "decrypted"))
    return DecryptConfig(
        enabled=os.environ.get("ENABLE_UPLOAD_DECRYPTION", "False").lower() == "true",
        server_url=os.environ.get("DECRYPT_SERVER_URL", "").strip(),
        timeout_seconds=int(os.environ.get("DECRYPT_TIMEOUT_SECONDS", "120")),
        output_dir=output_dir,
    )


def decrypt_uploaded_file(
    input_path: str,
    original_filename: str,
    content_type: str | None,
    metadata: dict | None = None,
    *,
    config: DecryptConfig | None = None,
) -> DecryptResult:
    config = config or load_decrypt_config()
    if not config.enabled:
        return DecryptResult(
            output_path=Path(input_path),
            filename=original_filename,
            content_type=content_type,
            size=Path(input_path).stat().st_size,
            message="upload decryption disabled",
        )
    if not config.server_url:
        raise DecryptError("已启用上传解密，但未配置 DECRYPT_SERVER_URL")

    config.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = config.output_dir / Path(input_path).name

    client = load_client_module()
    if not hasattr(client, "decrypt_file"):
        raise DecryptError("decrypt.client 缺少 decrypt_file()")

    payload = client.decrypt_file(
        input_path=input_path,
        output_path=str(output_path),
        metadata={
            **(metadata or {}),
            "decrypt_server_url": config.server_url,
            "timeout_seconds": config.timeout_seconds,
            "original_filename": original_filename,
            "content_type": content_type,
        },
    )
    if not isinstance(payload, dict):
        raise DecryptError("解密结果必须是 dict")

    return validate_decrypt_result(payload, original_filename=original_filename, original_content_type=content_type)
```

- [ ] **步骤 3：补根目录 `decrypt/` 的固定骨架**

```python
# decrypt/__init__.py
"""Company-specific upload decryption integration package."""
```

```python
# decrypt/client.py
from __future__ import annotations


def decrypt_file(input_path: str, output_path: str, metadata: dict | None = None) -> dict:
    raise RuntimeError(
        "请先在 decrypt/client.py 中接入公司的解密服务，再启用 ENABLE_UPLOAD_DECRYPTION"
    )
```

- [ ] **步骤 4：运行适配层测试，确认这部分先绿起来**

运行：

```bash
pytest tests/test_upload_decryption.py -k "validate_decrypt_result or decrypt" -q
```

预期：

- 解密结果校验测试通过
- 路由测试如果还没绿，失败点应该已经从 import 错误变成真正的流程错误

- [ ] **步骤 5：提交适配层和根目录骨架**

```bash
git add backend/open_webui/utils/decrypt.py decrypt/__init__.py decrypt/client.py tests/test_upload_decryption.py
git commit -m "feat: add upload decryption adapter"
```

## 任务 3：把上传主流程接到强制解密上

**文件：**
- 修改：`backend/open_webui/routers/files.py`
- 测试：`tests/test_upload_decryption.py`

- [ ] **步骤 1：在上传路由里引入解密适配层**

```python
from open_webui.utils.decrypt import DecryptError, decrypt_uploaded_file
```

- [ ] **步骤 2：加一个中间文件清理辅助函数**

```python
def _delete_local_file_if_exists(path: str | os.PathLike | None) -> None:
    if not path:
        return
    try:
        resolved = Path(path)
        if resolved.is_file():
            resolved.unlink()
    except Exception:
        log.warning("Failed to delete temporary upload artifact: %s", path)
```

- [ ] **步骤 3：改 `upload_file_handler()`，上传后立刻解密**

```python
        contents, file_path = Storage.upload_file(
            file.file,
            filename,
            {
                'OpenWebUI-User-Email': user.email,
                'OpenWebUI-User-Id': user.id,
                'OpenWebUI-User-Name': user.name,
                'OpenWebUI-File-Id': id,
            },
        )

        decrypted = decrypt_uploaded_file(
            input_path=file_path,
            original_filename=name,
            content_type=(file.content_type if isinstance(file.content_type, str) else None),
            metadata=file_metadata,
        )

        if str(decrypted.output_path) != file_path:
            _delete_local_file_if_exists(file_path)

        file_path = str(decrypted.output_path)
        name = decrypted.filename
        content_type = decrypted.content_type
        contents = Path(file_path).read_bytes()
```

- [ ] **步骤 4：文件入库时改用解密后的元数据**

```python
        file_item = Files.insert_new_file(
            user.id,
            FileForm(
                **{
                    'id': id,
                    'filename': name,
                    'path': file_path,
                    'data': {
                        **({'status': 'pending'} if process else {}),
                    },
                    'meta': {
                        'name': name,
                        'content_type': content_type,
                        'size': len(contents),
                        'data': file_metadata,
                    },
                }
            ),
            db=db,
        )
```

- [ ] **步骤 5：把解密失败转成明确的 HTTP 400 上传失败**

```python
    except DecryptError as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(f'文件解密失败: {e}'),
        )
```

- [ ] **步骤 6：运行上传路由测试，确认主流程已经绿了**

运行：

```bash
pytest tests/test_upload_decryption.py -k upload_file_handler -q
```

预期：

- 成功用例通过，说明 `Files.insert_new_file()` 吃到的是解密后的路径和大小
- 失败用例通过，说明解密失败时直接返回上传错误

- [ ] **步骤 7：提交上传主流程接入**

```bash
git add backend/open_webui/routers/files.py tests/test_upload_decryption.py
git commit -m "feat: decrypt uploads before processing"
```

## 任务 4：补运行时配置、Windows 服务导出和中文接入说明

**文件：**
- 修改：`backend/open_webui/config.py`
- 修改：`start.py`
- 修改：`start_prod.py`
- 修改：`service/open_webui-service.json`
- 新建：`decrypt/README.md`
- 测试：`tests/test_upload_decryption.py`
- 测试：`tests/test_start.py`

- [ ] **步骤 1：在后端配置里增加解密相关环境变量**

```python
ENABLE_UPLOAD_DECRYPTION = PersistentConfig(
    'ENABLE_UPLOAD_DECRYPTION',
    'files.upload_decryption.enable',
    os.environ.get('ENABLE_UPLOAD_DECRYPTION', 'False').lower() == 'true',
)
DECRYPT_SERVER_URL = PersistentConfig(
    'DECRYPT_SERVER_URL',
    'files.upload_decryption.server_url',
    os.environ.get('DECRYPT_SERVER_URL', ''),
)
DECRYPT_TIMEOUT_SECONDS = PersistentConfig(
    'DECRYPT_TIMEOUT_SECONDS',
    'files.upload_decryption.timeout_seconds',
    int(os.environ.get('DECRYPT_TIMEOUT_SECONDS', '120')),
)
DECRYPT_OUTPUT_DIR = PersistentConfig(
    'DECRYPT_OUTPUT_DIR',
    'files.upload_decryption.output_dir',
    os.environ.get('DECRYPT_OUTPUT_DIR', f'{UPLOAD_DIR}/decrypted'),
)
```

- [ ] **步骤 2：在 `start.py` 和 `start_prod.py` 提供默认值**

```python
decrypt_output_dir = str((ROOT / 'backend' / 'data' / 'uploads' / 'decrypted').resolve())
env.setdefault('ENABLE_UPLOAD_DECRYPTION', 'True')
env.setdefault('DECRYPT_SERVER_URL', '')
env.setdefault('DECRYPT_TIMEOUT_SECONDS', '120')
env.setdefault('DECRYPT_OUTPUT_DIR', decrypt_output_dir)
```

```python
os.environ.setdefault('ENABLE_UPLOAD_DECRYPTION', 'True')
os.environ.setdefault('DECRYPT_SERVER_URL', '')
os.environ.setdefault('DECRYPT_TIMEOUT_SECONDS', '120')
os.environ.setdefault('DECRYPT_OUTPUT_DIR', str((ROOT / 'backend' / 'data' / 'uploads' / 'decrypted').resolve()))
```

- [ ] **步骤 3：让生产服务模式也导出这些变量，并更新示例 JSON**

```python
        'ENABLE_UPLOAD_DECRYPTION',
        'DECRYPT_SERVER_URL',
        'DECRYPT_TIMEOUT_SECONDS',
        'DECRYPT_OUTPUT_DIR',
```

```json
  "ENABLE_UPLOAD_DECRYPTION": "True",
  "DECRYPT_SERVER_URL": "",
  "DECRYPT_TIMEOUT_SECONDS": "120",
  "DECRYPT_OUTPUT_DIR": "C:\\Users\\ArcherWoo\\Desktop\\open-webui-main\\open-webui-main\\backend\\data\\uploads\\decrypted"
```

- [ ] **步骤 4：补一份你真正能看懂、能操作的中文 `decrypt/README.md`**

```md
# 本地上传解密接入说明

这个目录专门用来放公司内网环境里的上传解密代码。

当前项目已经做了适配，所有通过 `/api/v1/files/` 的上传都会先调用 `decrypt/client.py` 里的 `decrypt_file()`。

你必须实现这个函数：

```python
def decrypt_file(input_path: str, output_path: str, metadata: dict | None = None) -> dict:
    ...
```

建议返回：

```python
{
    "success": True,
    "output_path": output_path,
    "filename": "解密后的文件名.docx",
    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "message": "ok"
}
```

如果调用公司解密服务失败，建议直接抛异常或返回：

```python
{"success": False, "message": "解密服务返回失败"}
```
```

- [ ] **步骤 5：补启动默认值测试**

```python
def test_build_runtime_env_sets_decrypt_defaults():
    args = SimpleNamespace(host='0.0.0.0', port=8080, enable_base_model_cache=False, online=False)

    env = start.build_runtime_env(
        Path('C:/fake/python.exe'),
        args,
        start.PipMirror(),
        start.NpmRegistry(),
    )

    assert env['ENABLE_UPLOAD_DECRYPTION'] == 'True'
    assert env['DECRYPT_SERVER_URL'] == ''
    assert env['DECRYPT_TIMEOUT_SECONDS'] == '120'
    assert env['DECRYPT_OUTPUT_DIR'].endswith('backend\\data\\uploads\\decrypted')
```

- [ ] **步骤 6：运行这一轮定向验证**

运行：

```bash
pytest tests/test_upload_decryption.py tests/test_start.py -q
```

预期：

- `tests/test_start.py` 通过，说明启动入口默认值已生效
- `tests/test_upload_decryption.py` 通过，说明上传自动解密逻辑和失败策略已生效

- [ ] **步骤 7：提交配置和中文说明**

```bash
git add backend/open_webui/config.py start.py start_prod.py service/open_webui-service.json decrypt/README.md tests/test_upload_decryption.py tests/test_start.py
git commit -m "docs: add upload decryption setup guide"
```

## 自检

- 需求覆盖：
  - 统一上传自动解密：任务 3
  - 根目录 `decrypt/` 固定接口和中文说明：任务 2、任务 4
  - 启动默认值与服务导出：任务 4
  - 解密失败即上传失败：任务 1、任务 3
- 占位符检查：
  - 没有 `TODO`、`TBD`、`后面再说` 这种空话
  - 每一步都给了具体文件、代码和命令
- 名称一致性：
  - 统一使用 `decrypt_uploaded_file()`、`DecryptResult`、`decrypt_file()` 这几个名称

## 执行交接

计划已保存到 `docs/superpowers/plans/2026-04-18-upload-decryption.md`。

后续执行方式有两种：

1. `Subagent-Driven`
   - 每个任务派独立子 agent 做，再逐步 review
2. `Inline Execution`
   - 在当前会话里直接按计划一步步做

你前面已经明确让我继续实施，所以默认继续走 `Inline Execution`。
