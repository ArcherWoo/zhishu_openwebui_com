from __future__ import annotations


def decrypt_file(input_path: str, output_path: str, metadata: dict | None = None) -> dict:
    raise RuntimeError(
        '请先在 decrypt/client.py 中接入公司的解密服务，再启用 ENABLE_UPLOAD_DECRYPTION'
    )
