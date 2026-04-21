# 上传解密接入说明

这个目录用于接入公司内网的文件解密服务。

当前项目已经接好了上传入口，所有通过 `/api/v1/files/` 的文件上传，都会先调用：

- [client.py](/C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/decrypt/client.py) 里的 `decrypt_file()`

也就是说，下面这些场景都会先走这里的解密逻辑：

- 聊天里上传附件
- 知识库里上传文件
- 其他复用同一上传接口的场景

只有解密成功后，系统才会继续做文档解析、向量化和问答。

## 你真正要改哪个文件

你真正需要实现的是：

- [client.py](/C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/decrypt/client.py)

当前它只是一个占位文件，默认会直接报错。

## 必须实现的函数

你需要提供这个函数：

```python
def decrypt_file(input_path: str, output_path: str, metadata: dict | None = None) -> dict:
    ...
```

## 参数说明

### `input_path`

- 当前上传文件在本机上的临时路径
- 这是你要送去解密服务的输入文件

### `output_path`

- 你需要把“解密后的文件”写到这个路径
- 建议直接按这个路径输出，不要自己改名改位置

### `metadata`

里面会带一些上下文信息，常见包括：

- `decrypt_server_url`
- `timeout_seconds`
- `original_filename`
- `content_type`

如果前端上传时额外带了别的 metadata，也可能一起传进来。

## 推荐返回格式

解密成功时，建议返回：

```python
{
    "success": True,
    "output_path": output_path,
    "filename": "解密后的真实文件名.docx",
    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "message": "ok"
}
```

### 字段含义

- `success`
  - 必须是 `True`
- `output_path`
  - 必须指向真实存在的解密后文件
- `filename`
  - 可选
  - 如果你希望系统后续显示解密后的真实文件名，就返回它
- `content_type`
  - 可选
  - 如果解密后文件类型更明确，建议一起返回
- `message`
  - 可选
  - 主要用于日志和排查

## 失败时怎么处理

失败时推荐两种方式，任选一种：

### 方式 A：直接抛异常

```python
raise RuntimeError("解密服务返回失败")
```

### 方式 B：返回失败结果

```python
{
    "success": False,
    "message": "解密服务返回失败"
}
```

这两种方式都会让当前上传直接失败，不会继续进入文档解析流程。

## 一个最简单的接入模板

下面这个例子演示的是“调用公司内网 HTTP 解密服务”的常见写法：

```python
from __future__ import annotations

from pathlib import Path
import requests


def decrypt_file(input_path: str, output_path: str, metadata: dict | None = None) -> dict:
    metadata = metadata or {}
    server_url = metadata.get("decrypt_server_url", "").strip()
    timeout_seconds = int(metadata.get("timeout_seconds", 120))

    if not server_url:
        raise RuntimeError("未提供 decrypt_server_url")

    input_file = Path(input_path)
    target_file = Path(output_path)
    target_file.parent.mkdir(parents=True, exist_ok=True)

    with input_file.open("rb") as f:
        response = requests.post(
            server_url,
            files={"file": (input_file.name, f)},
            timeout=timeout_seconds,
        )

    response.raise_for_status()
    target_file.write_bytes(response.content)

    return {
        "success": True,
        "output_path": str(target_file),
        "filename": metadata.get("original_filename") or input_file.name,
        "content_type": metadata.get("content_type"),
        "message": "ok",
    }
```

你们如果不是这种接口形式，也没关系。主程序并不关心你中间怎么调，只关心最终结果是不是：

1. 成功把解密文件写到了 `output_path`
2. 返回了 `success=True`
3. `output_path` 指向的文件真实存在

## 当前默认配置

项目现在已经支持这些环境变量：

- `ENABLE_UPLOAD_DECRYPTION`
- `DECRYPT_SERVER_URL`
- `DECRYPT_TIMEOUT_SECONDS`
- `DECRYPT_OUTPUT_DIR`

最少要配好的是：

- `DECRYPT_SERVER_URL`

例如：

```text
http://10.10.10.20:8088/decrypt
```

## 自测建议

最简单的自测步骤：

1. 在 [client.py](/C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/decrypt/client.py) 里接好你们公司的解密服务
2. 配好 `DECRYPT_SERVER_URL`
3. 重启 Open WebUI
4. 上传一个原本因为加密而无法解析的文件
5. 观察是否能继续进入解析链路

如果上传时报“文件解密失败”，说明拦截逻辑已经生效，但你的解密实现还需要继续排查。

## 常见错误

### 1. 只返回 success，没有真的写文件

错误示例：

```python
return {"success": True, "output_path": output_path}
```

但实际 `output_path` 对应文件并不存在。

这种情况下，主程序仍然会判定失败。

### 2. 解密后写到了别的目录，但没有把真实路径返回回来

如果你自己改了输出目录，一定要把真实文件路径放回 `output_path`。

### 3. 没配 `DECRYPT_SERVER_URL`

如果启用了自动解密但没有配置服务地址，上传会直接失败。

### 4. 解密服务超时

默认超时是 `120` 秒。

如果你们处理大文件比较慢，可以适当调大 `DECRYPT_TIMEOUT_SECONDS`。

## 建议

第一版接入时，先做到这三件事就够了：

1. 能稳定把输入文件送到公司解密服务
2. 能把解密结果写回 `output_path`
3. 失败时明确抛错，不要“假成功”

等主链路跑通之后，再考虑：

- 增加认证头
- 增加重试
- 增加任务轮询
- 增加详细日志
