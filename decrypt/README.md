# 本地上传解密接入说明

这个目录专门用来放公司内网环境里的上传解密代码。

当前项目已经做了适配，所有通过 `/api/v1/files/` 的上传都会先调用 [client.py](/c:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/decrypt/client.py) 里的 `decrypt_file()`。  
也就是说，不管是：

- 聊天里上传附件
- 知识库里上传文件
- 频道、笔记等复用同一上传接口的场景

都会先走这里的解密逻辑，解密成功后才会继续文档解析和知识库入库。

## 一、你需要改哪个文件

你真正要改的是：

- [client.py](/c:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/decrypt/client.py)

当前这个文件只是一个占位骨架，默认会直接报错。  
你需要把它改成“调用公司内网亿赛通解密服务”的真实实现。

## 二、必须实现的固定函数

你必须提供这个函数：

```python
def decrypt_file(input_path: str, output_path: str, metadata: dict | None = None) -> dict:
    ...
```

参数说明：

- `input_path`
  - 当前上传文件在本机上的临时路径
  - 这是你要拿去解密的原始输入文件
- `output_path`
  - 你应该把“解密后的文件”写到这个路径
  - 推荐直接按这个路径输出，不要自己乱改
- `metadata`
  - 额外上下文信息
  - 里面会带上：
    - `decrypt_server_url`
    - `timeout_seconds`
    - `original_filename`
    - `content_type`
  - 如果前端上传时额外带了别的 metadata，这里也可能一起带进来

## 三、推荐返回格式

解密成功时，建议返回：

```python
{
    "success": True,
    "output_path": output_path,
    "filename": "解密后的文件名.docx",
    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "message": "ok"
}
```

字段说明：

- `success`
  - 必须是 `True`
- `output_path`
  - 必须是已经真实写出来的解密后文件路径
- `filename`
  - 可选
  - 如果你希望上传后系统展示的文件名改成解密后的名字，可以返回它
- `content_type`
  - 可选
  - 如果解密后文件类型和原来不同，建议一起返回
- `message`
  - 可选
  - 主要用于日志或排错

## 四、失败时怎么返回

失败时有两种推荐方式。

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

这两种方式都会让当前上传直接失败，不会继续进入文档解析和知识库流程。

## 五、一个最简单的接入模板

下面这个模板演示的是“调用公司内网 HTTP 解密服务”的常见写法。  
你可以按你们实际接口改字段名和认证方式。

```python
from __future__ import annotations

from pathlib import Path
import shutil
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

    # 下面只是示例：
    # 如果你们服务直接返回解密后的二进制文件，可以这么写
    target_file.write_bytes(response.content)

    return {
        "success": True,
        "output_path": str(target_file),
        "filename": metadata.get("original_filename") or input_file.name,
        "content_type": metadata.get("content_type"),
        "message": "ok",
    }
```

## 六、如果你们服务不是直接返回文件

有些企业服务的返回方式可能不是“直接返回解密后的文件流”，而是：

- 先上传文件
- 返回任务 ID
- 再轮询状态
- 最后下载解密后的文件

那也没问题，你只要保证最后：

1. 真的把解密后的文件写到 `output_path`
2. 返回 `success=True`
3. 返回的 `output_path` 指向真实存在的文件

主程序不关心你中间怎么调用，只看最终结果。

## 七、当前项目的默认配置

当前项目已经默认设置了这些环境变量：

- `ENABLE_UPLOAD_DECRYPTION=True`
- `DECRYPT_SERVER_URL=`
- `DECRYPT_TIMEOUT_SECONDS=120`
- `DECRYPT_OUTPUT_DIR=<项目根目录>/backend/data/uploads/decrypted`

你部署前至少要把：

- `DECRYPT_SERVER_URL`

配成你们公司解密服务的实际地址，例如：

```text
http://10.10.10.20:8088/decrypt
```

## 八、怎么自测

最简单的自测方法：

1. 先在 [client.py](/c:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/decrypt/client.py) 里接好你们公司的解密服务。
2. 确认 `DECRYPT_SERVER_URL` 已配置。
3. 重启 Open WebUI。
4. 在聊天里上传一个平时会因为加密而无法解析的文档。
5. 观察结果：
   - 如果上传成功并能继续解析，说明解密链路生效
   - 如果直接报“文件解密失败”，说明程序已经正确拦截，但你需要继续排查企业解密服务

## 九、最常见的错误

### 1. 只返回了 success，没有真的写出文件

错误示例：

```python
return {"success": True, "output_path": output_path}
```

但其实 `output_path` 对应的文件并不存在。  
这种情况下主程序会判定为失败。

### 2. 解密后写到了别的目录，却没把真实路径返回回来

如果你自己改了输出路径，一定要把真实文件路径返回在 `output_path` 里。

### 3. 没配 `DECRYPT_SERVER_URL`

如果启用了上传自动解密，但没配置服务地址，上传会直接失败。

### 4. 解密服务超时

默认超时是 `120` 秒。  
如果你们服务处理大文件很慢，可以适当调大 `DECRYPT_TIMEOUT_SECONDS`。

## 十、建议

第一版接入时，建议先做到这三点就够了：

1. 能稳定把输入文件送到公司解密服务
2. 能把解密结果写回 `output_path`
3. 失败时明确抛错，不要“假成功”

等主链路跑通之后，再考虑：

- 增加认证头
- 增加重试
- 增加任务轮询
- 增加详细日志
