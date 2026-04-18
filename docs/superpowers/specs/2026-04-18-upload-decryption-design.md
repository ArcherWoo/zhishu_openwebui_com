# 文件上传自动解密接入设计

## 目标

为公司内网部署场景增加一套统一的“上传后自动解密”机制，满足以下需求：

- 聊天附件上传时，文件在进入内容解析前自动解密
- 知识库上传文件时，文件在进入内容解析和向量化前自动解密
- 解密逻辑与 Open WebUI 主流程解耦，集中放在仓库根目录的 `decrypt/` 目录中维护
- 调用公司内网现有的“亿赛通解密服务器 IP+端口”即可完成解密，不依赖外网
- 解密失败时直接中断上传，避免后续产生未解密文件、脏索引或错误知识库数据
- 为后续接入方提供一份中文 README，明确如何填入企业解密调用代码

## 范围

本次设计覆盖：

- 原始文件上传主入口的统一解密接入
- 聊天、频道、笔记、知识库等所有复用 `/api/v1/files/` 的上传场景
- 上传成功后的内容解析、RAG 入库、知识库批量添加对“解密后文件”的复用
- 根目录 `decrypt/` 目录结构、固定 Python 接口与中文说明文档
- 启动配置项与默认行为

本次不覆盖：

- 按文件类型有选择地跳过解密
- 保留原始密文副本
- 解密结果缓存
- 多套解密后端切换
- 终端文件管理器等与业务上传无关的第三方文件上传接口

## 现状与问题

当前项目里真正的原始文件上传主入口集中在 [backend/open_webui/routers/files.py](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/backend/open_webui/routers/files.py) 的 `upload_file()` / `upload_file_handler()`。

前端多个页面虽然看起来是不同上传入口，但最终都复用 [src/lib/apis/files/index.ts](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/src/lib/apis/files/index.ts) 里的 `uploadFile()`，再调用同一个后端 `/api/v1/files/` 接口，主要包括：

- 聊天上传
- 频道消息上传
- 笔记附件上传
- 知识库界面直接上传文件
- 从 Google Drive / OneDrive 选择后再上传

知识库的“添加文件到库”并不是重新上传二进制文件，而是对已经上传完成的 `file_id` 继续执行 `process_file()` 和批量向量化。因此只要统一上传入口拿到的是解密后的文件，后续知识库链路天然就会复用解密结果。

当前问题在于：

- 公司内网 90% 文件是亿赛通加密文件，直接进入现有解析链路会失败
- 如果把解密逻辑分散插到聊天、知识库等多个入口，容易漏改和后续维护困难
- 如果允许解密失败后继续上传，会把密文文件写入系统并污染解析、预览和知识库索引

## 设计原则

### 1. 统一入口优先

解密只接在原始文件上传主入口，不在每个业务页面各写一套逻辑。

### 2. 解密失败即上传失败

既然内网绝大多数文件都需要解密，失败时应尽早中断，不允许携带密文继续进入后续链路。

### 3. 主流程与企业逻辑解耦

Open WebUI 主体只依赖一个稳定的 Python 接口，不直接感知亿赛通服务的请求细节。

### 4. 明文成为系统唯一后续输入

上传成功后，后续解析、预览、向量化和知识库复用都只使用解密后的文件，避免密文和明文混用。

### 5. 最小侵入

优先复用现有 `upload_file_handler()` -> `process_uploaded_file()` -> `process_file()` 主链路，不改动知识库和 RAG 的核心行为。

## 方案选择

### 方案 A：统一上传入口前置解密

- 在 `upload_file_handler()` 中完成落盘后立即解密
- 解密成功后再继续写入文件记录和后续处理
- 解密失败时直接返回上传失败

优点：

- 所有复用 `/api/v1/files/` 的上传场景自动生效
- 知识库、聊天、笔记、频道等不需要分别实现
- 后续解析、RAG、知识库逻辑可以完全复用现有主流程

缺点：

- 上传链路会增加一个同步解密步骤
- 解密服务不可用时上传会直接受影响

### 方案 B：解析前再解密

- 文件先正常上传保存
- 只在 `process_uploaded_file()` 或 `process_file()` 前解密

优点：

- 对“只上传不处理”的场景侵入较小

缺点：

- 系统中仍会保存密文文件
- 预览、下载、知识库复用和二次处理容易出现混乱
- 一旦有其他地方绕过解析链路，仍可能使用密文文件

### 方案 C：每个上传场景分别接解密

优点：

- 每个界面可独立控制

缺点：

- 改动分散
- 极易漏入口
- 后续维护成本最高

本次采用方案 A。

## 详细设计

### 一、上传链路改造

统一修改 [backend/open_webui/routers/files.py](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/backend/open_webui/routers/files.py) 的 `upload_file_handler()`。

目标顺序：

1. 接收上传文件
2. 先按现有方式把原始上传内容落到存储
3. 立刻调用统一解密适配层
4. 若解密成功，则以后续“解密后的文件路径、文件大小、可选文件名/类型”继续构建文件记录
5. 再执行现有 `Files.insert_new_file(...)`
6. 后续继续走现有 `process_uploaded_file()` 和 `process_file()` 链路

失败顺序：

1. 文件落盘后调用解密
2. 解密服务返回失败、超时、响应不合法、输出文件不存在，均视为解密失败
3. 立即终止上传
4. 清理本次上传产生的中间文件
5. 返回明确的上传错误信息
6. 不写入有效 `Files` 记录，不触发后续解析和知识库入库

### 二、统一解密适配层

新增一个后端封装模块：

- [backend/open_webui/utils/decrypt.py](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/backend/open_webui/utils/decrypt.py)

职责：

- 读取解密相关配置
- 按固定接口调用根目录 `decrypt/client.py`
- 统一处理异常、超时、返回值校验
- 返回主流程可直接消费的解密结果

推荐提供的核心方法：

```python
def decrypt_uploaded_file(
    input_path: str,
    original_filename: str,
    content_type: str | None,
    metadata: dict | None = None,
) -> DecryptResult:
    ...
```

`DecryptResult` 应至少包含：

- `output_path`
- `filename`
- `content_type`
- `size`
- `message`

### 三、根目录 `decrypt/` 目录

新增根目录结构：

```text
decrypt/
├─ __init__.py
├─ client.py
└─ README.md
```

职责划分：

- `client.py`
  - 只负责接企业解密服务
  - 由项目使用者填入调用公司内网 IP+端口的具体实现
- `README.md`
  - 用中文说明如何实现和替换 `client.py`
  - 说明函数签名、输入输出、异常行为和本地自测方法

### 四、固定 Python 接口

`decrypt/client.py` 统一暴露固定函数：

```python
def decrypt_file(input_path: str, output_path: str, metadata: dict | None = None) -> dict:
    """
    返回格式：
    {
        "success": True,
        "output_path": "...",
        "filename": "...",      # optional
        "content_type": "...",  # optional
        "message": "...",       # optional
    }
    """
```

约束：

- 主程序只调用这个函数，不关心内部是否用 `requests`、企业 SDK 或其他协议
- `output_path` 必须指向一个真实存在的解密后文件
- `success=False` 或抛异常都视为解密失败
- 返回值结构不合法也视为解密失败

### 五、文件保留策略

默认不保留原始密文文件。

设计行为：

- 原始上传文件只作为解密输入
- 解密成功后，系统后续只认解密后的文件
- 原始密文中间文件清理掉

原因：

- 避免密文与明文并存导致预览、下载和知识库复用混乱
- 减少误把密文再次送入解析链路的风险
- 更符合“上传成功即代表系统已拿到可处理文件”的直觉

### 六、配置项设计

新增显式配置项，并在启动入口提供默认值：

- `ENABLE_UPLOAD_DECRYPTION=True`
- `DECRYPT_SERVER_URL=""`
- `DECRYPT_TIMEOUT_SECONDS=120`
- `DECRYPT_OUTPUT_DIR=<项目根目录>/data/uploads/decrypted` 或等效上传目录内子目录

行为约束：

- `ENABLE_UPLOAD_DECRYPTION=True` 时，所有原始文件上传都自动尝试解密
- 若 `DECRYPT_SERVER_URL` 未配置但启用了自动解密，上传应直接失败并给出明确提示
- `DECRYPT_TIMEOUT_SECONDS` 用于保护上传线程，避免长期卡死

### 七、上传来源覆盖范围

以下前端上传场景由于复用 `/api/v1/files/`，会自动获得解密能力：

- [src/lib/components/chat/MessageInput.svelte](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/src/lib/components/chat/MessageInput.svelte)
- [src/lib/components/chat/Chat.svelte](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/src/lib/components/chat/Chat.svelte)
- [src/lib/components/channel/MessageInput.svelte](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/src/lib/components/channel/MessageInput.svelte)
- [src/lib/components/notes/NoteEditor.svelte](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/src/lib/components/notes/NoteEditor.svelte)
- [src/lib/components/workspace/Knowledge/KnowledgeBase.svelte](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/src/lib/components/workspace/Knowledge/KnowledgeBase.svelte)
- [src/lib/components/workspace/Models/Knowledge.svelte](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/src/lib/components/workspace/Models/Knowledge.svelte)

以下知识库入口不会单独解密，因为它们复用的本来就是“已上传文件”：

- [backend/open_webui/routers/knowledge.py](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/backend/open_webui/routers/knowledge.py) 的 `add_file_to_knowledge_by_id()`
- [backend/open_webui/routers/knowledge.py](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/backend/open_webui/routers/knowledge.py) 的 `add_files_to_knowledge_batch()`

### 八、错误处理与用户反馈

上传接口在解密失败时统一返回“文件解密失败”语义的错误。

后端错误分类建议：

- 解密服务连接失败
- 解密服务超时
- 解密服务返回失败状态
- 解密输出文件不存在
- 解密返回值结构不合法

前端不需要新增复杂状态机，只需复用现有上传失败提示即可，但后端返回文案要足够明确，便于内网排障。

### 九、README 设计

[decrypt/README.md](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/decrypt/README.md) 至少应包含：

- 这个目录的用途
- 当前项目在哪个上传环节自动调用解密
- `decrypt/client.py` 的固定函数签名
- `input_path`、`output_path`、`metadata` 的含义
- 返回值字段说明
- 成功返回示例
- 失败返回示例
- 如何调用公司内网亿赛通解密服务
- 如何填写服务 IP、端口、认证信息
- 超时和异常处理建议
- 如何本地自测
- 最常见的错误与排查方式

## 测试策略

本轮实现建议覆盖以下测试：

1. 上传成功时会调用解密适配层，并把解密后的文件继续写入文件记录
2. 解密失败时上传接口直接失败，不写入有效文件记录
3. 解密失败时不会进入 `process_uploaded_file()` 和 `process_file()`
4. 知识库后续处理复用已解密文件，不需要二次解密
5. `decrypt/client.py` 返回结构缺字段时能被正确识别为失败
6. 解密超时能返回明确错误信息

如果现有测试环境不方便覆盖真实解密服务，应通过 mock 固定 Python 接口来验证主流程行为。

## 风险与约束

### 1. 解密服务可用性成为上传前置依赖

因为选择了“自动解密且失败即失败”，所以企业解密服务的可用性会直接影响上传能力。

### 2. 上传耗时会增加

解密是同步前置步骤，大文件上传的总耗时会增加，需要合理设置超时。

### 3. 存储提供方差异

当前项目支持 local / S3 / GCS / Azure 等存储。实现时应确保解密逻辑使用的是一个本地可读写临时文件路径，而不是直接对远程对象路径做原地处理。

### 4. 输出文件名与 MIME 可能变化

某些企业解密服务可能输出新文件名、改变扩展名或需要重新识别 MIME 类型，实现时应允许 `decrypt/client.py` 覆盖这些信息。

## 验收标准

满足以下条件即可认为设计落地成功：

- 所有通过 `/api/v1/files/` 的上传都会自动解密
- 聊天附件上传与知识库上传都覆盖到
- 解密失败时上传直接失败，不进入解析和知识库流程
- 后续 `process_uploaded_file()` 和 `process_file()` 处理的是解密后的文件
- 仓库根目录新增 `decrypt/` 目录，并提供可替换的 `client.py` 骨架
- `decrypt/README.md` 能指导内网环境接入企业解密服务
- 启动入口具备清晰的解密配置项
