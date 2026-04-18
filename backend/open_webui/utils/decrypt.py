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


def load_client_module():
    return importlib.import_module('decrypt.client')


def load_decrypt_config(source: Any = None) -> DecryptConfig:
    def get_value(key: str, default: Any = None) -> Any:
        if source is not None and hasattr(source, key):
            return getattr(source, key)
        return os.environ.get(key, default)

    root = Path(__file__).resolve().parents[3]
    output_dir = Path(get_value('DECRYPT_OUTPUT_DIR', root / 'backend' / 'data' / 'uploads' / 'decrypted'))
    timeout_seconds = int(get_value('DECRYPT_TIMEOUT_SECONDS', '120') or 120)

    return DecryptConfig(
        enabled=str(get_value('ENABLE_UPLOAD_DECRYPTION', 'False')).lower() == 'true',
        server_url=str(get_value('DECRYPT_SERVER_URL', '') or '').strip(),
        timeout_seconds=timeout_seconds,
        output_dir=output_dir,
    )


def validate_decrypt_result(
    payload: dict[str, Any],
    original_filename: str,
    original_content_type: str | None,
) -> DecryptResult:
    if not payload.get('success'):
        raise DecryptError(payload.get('message') or '文件解密失败')

    output_path_value = payload.get('output_path')
    if not output_path_value:
        raise DecryptError('解密结果缺少 output_path')

    output_path = Path(output_path_value)
    if not output_path.is_file():
        raise DecryptError('解密结果输出文件不存在')

    filename = payload.get('filename') or output_path.name or original_filename
    content_type = payload.get('content_type') or original_content_type

    return DecryptResult(
        output_path=output_path,
        filename=filename,
        content_type=content_type,
        size=output_path.stat().st_size,
        message=payload.get('message'),
    )


def decrypt_uploaded_file(
    input_path: str,
    original_filename: str,
    content_type: str | None,
    metadata: dict | None = None,
    *,
    config: DecryptConfig | Any | None = None,
) -> DecryptResult:
    if config is None or not isinstance(config, DecryptConfig):
        config = load_decrypt_config(config)

    input_file = Path(input_path)
    if not input_file.is_file():
        raise DecryptError(f'待解密文件不存在: {input_path}')

    if not config.enabled:
        return DecryptResult(
            output_path=input_file,
            filename=original_filename,
            content_type=content_type,
            size=input_file.stat().st_size,
            message='upload decryption disabled',
        )

    if not config.server_url:
        raise DecryptError('已启用上传解密，但未配置 DECRYPT_SERVER_URL')

    config.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = config.output_dir / input_file.name

    client = load_client_module()
    if not hasattr(client, 'decrypt_file'):
        raise DecryptError('decrypt.client 缺少 decrypt_file()')

    payload = client.decrypt_file(
        input_path=str(input_file),
        output_path=str(output_path),
        metadata={
            **(metadata or {}),
            'decrypt_server_url': config.server_url,
            'timeout_seconds': config.timeout_seconds,
            'original_filename': original_filename,
            'content_type': content_type,
        },
    )

    if not isinstance(payload, dict):
        raise DecryptError('解密结果必须是 dict')

    return validate_decrypt_result(
        payload,
        original_filename=original_filename,
        original_content_type=content_type,
    )
