# 离线 PPT Markdown 解析方案设计

## 目标

为公司内网的 `Windows + CPU` 部署环境提供一条**完全离线、稳定可控、可运维**的 PowerPoint 解析链路，使 `.pptx` 与 `.ppt` 文件在以下场景中都能跑通：

- 聊天附件上传后参与问答
- 知识库文件导入
- 解密后的 PowerPoint 文件进入向量数据库
- 后续通过 LLM 正常检索与问答

本次设计的重点不是“支持更多文档类型”，而是**单独把 PowerPoint 这一条链路做稳**，避免再次影响已经正常的 Excel / Word / TXT 流程。

## 设计结论

采用以下方案：

- `PPTX`：解密后直接交给本地 `MarkItDown` 转换为 Markdown
- `PPT`：解密后先在本机使用 `LibreOffice/soffice` 转换为临时 `PPTX`，再统一交给本地 `MarkItDown`
- `MarkItDown` 失败时，退回项目内增强版 `python-pptx` fallback，仅提取基础文本并拼装为简单 Markdown
- 整个 PowerPoint 解析过程**不新增独立 HTTP 服务**，全部以内嵌本地调用方式完成
- 解析结果继续复用现有 `process_file -> save_docs_to_vector_db -> embedding -> vector DB -> retrieval` 链路

一句话概括：

> `PPT` 和 `PPTX` 的统一 Markdown 解析器都是 `MarkItDown`，只是 `.ppt` 在进入 `MarkItDown` 之前先做一次本地格式转换。

## 适用约束

本方案基于以下前提成立：

- 部署环境为 `Windows + CPU`
- 服务器处于公司内网，不能依赖外网下载模型、词典或文档解析服务
- 允许随项目一起携带离线 Python 依赖包
- 允许额外安装本机软件，但不接受额外起常驻解析服务
- 允许为 `.ppt` 安装 `LibreOffice`

## 范围

本次覆盖：

- PowerPoint 上传与知识库导入的本地离线解析
- `.pptx -> Markdown`
- `.ppt -> .pptx -> Markdown`
- PowerPoint 解析失败时的 fallback
- PowerPoint 解析日志、超时与错误状态处理
- PowerPoint 离线依赖准备文档

本次不覆盖：

- PDF / 图片 / Markdown / 其他文件类型的解析重构
- 新增独立解析服务
- 更换现有 embedding 流程
- 重构现有解密流程
- 对外部 `datalab_marker` / `docling` / `mineru` 的服务化部署

## 现状与问题

### 1. 当前主流程本身是通的

从现有代码看，文件上传与解密完成后会继续进入现有文件处理链路：

- [files.py](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/backend/open_webui/routers/files.py)
- [retrieval.py](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/backend/open_webui/routers/retrieval.py)

也就是说，当前问题不是“上传主流程整体坏掉”，而是某些类型在进入 loader 后卡住。

### 2. Excel 与 PowerPoint 使用的是不同的解析依赖

在 [main.py](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/backend/open_webui/retrieval/loaders/main.py) 中：

- Excel 走 `UnstructuredExcelLoader` 或 `pandas` fallback
- PowerPoint 走 `UnstructuredPowerPointLoader`

这解释了为什么 Excel 全链路可用，而 PowerPoint 独立出问题。

### 3. 当前 PowerPoint 链路在内网环境下不够稳

现状风险主要有三类：

- `unstructured` 相关依赖在 `PPTX` 解析路径上容易触发 NLTK 资源检查或其他额外依赖
- 老 `.ppt` 需要依赖 `soffice` 转换，否则无法进入统一解析
- 当前异常可观测性不足，解析器内部卡住时，前端容易表现为持续转圈

因此，这条链路需要从“能解析”升级到“在内网环境下稳定可控地解析”。

## 核心原则

### 1. 不改主干，只替换 PowerPoint 解析层

上传、解密、文件入库、embedding、向量库写入、问答都继续复用现有流程。  
本次只替换 PowerPoint 的文档提取方式。

### 2. `PPT` 与 `PPTX` 统一使用 `MarkItDown`

PowerPoint 的最终 Markdown 产物必须来自同一套解析器，避免：

- `.pptx` 一套风格
- `.ppt` 另一套风格
- 同类文档在向量库中的结构差异过大

### 3. 失败要可见、可退、可恢复

任何 PowerPoint 处理失败都必须：

- 有明确日志
- 有明确失败状态
- 有可读错误信息
- 不允许出现无穷等待

### 4. 优先保证“稳定能进库”，其次才是格式精美

内网场景下优先级如下：

1. 能稳定解析
2. 能稳定进向量库
3. 能正常问答
4. Markdown 结构尽可能好

因此需要保留基础文本 fallback，避免主解析器失效时整条链断掉。

## 总体架构

### 目标架构

PowerPoint 文件进入系统后的处理路径如下：

1. 上传原始文件
2. 调用公司解密服务
3. 解密文件重新写回存储
4. `process_file()` 识别为 PowerPoint
5. 进入新的 `PowerPointMarkdownLoader`
6. 根据扩展名走不同分支
7. 统一得到 Markdown 字符串
8. 封装为 `Document`
9. 继续走现有 chunk / embedding / vector DB 流程

### 分支路径

#### `.pptx`

1. 解密后文件路径传入 `MarkItDownPowerPointLoader`
2. 本地 `MarkItDown` 输出 Markdown
3. 封装为 `Document(page_content=markdown, metadata=...)`
4. 进入现有向量化流程

#### `.ppt`

1. 解密后文件路径传入 `PowerPointConverter`
2. 本机 `soffice` 转为临时 `.pptx`
3. 将临时 `.pptx` 交给 `MarkItDownPowerPointLoader`
4. 输出 Markdown
5. 封装为 `Document`
6. 进入现有向量化流程

#### fallback

任一主路径失败时：

1. 记录失败原因
2. 尝试增强版 `python-pptx` fallback
3. 若 fallback 成功，则继续入库
4. 若 fallback 失败，则文件标记为 `failed`

## 组件拆分

本次建议新增 4 个边界清晰的组件。

### 1. `PowerPointConverter`

职责：

- 仅负责 `.ppt -> .pptx`
- 封装本机 `LibreOffice/soffice` 调用
- 管理临时目录
- 提供超时与错误信息

输入：

- `.ppt` 文件路径

输出：

- 转换后的临时 `.pptx` 路径

不负责：

- 文本解析
- Markdown 生成
- 向量化

### 2. `MarkItDownPowerPointLoader`

职责：

- 调用本地 `MarkItDown`
- 将 `.pptx` 转为 Markdown
- 标准化输出文本

输入：

- `.pptx` 文件路径

输出：

- Markdown 字符串

不负责：

- `.ppt` 转换
- 文件状态更新

### 3. `PowerPointMarkdownLoader`

职责：

- 作为 PowerPoint 统一入口
- 判断扩展名
- `.pptx` 直接走 `MarkItDown`
- `.ppt` 先转换再走 `MarkItDown`
- 在主路径失败时触发 fallback

输入：

- 文件名
- MIME 类型
- 文件路径

输出：

- `Document` 列表

### 4. `PowerPointFallbackLoader`

职责：

- 使用现有 `python-pptx` 做兜底文本抽取
- 输出基础 Markdown

适用场景：

- `MarkItDown` 安装缺失
- `MarkItDown` 调用失败
- 某些幻灯片结构导致主解析失败

注意：

- fallback 仅保证“文本可入库”
- 不保证版式与标题层级完全准确

## 文件与模块落位建议

建议在现有后端结构中新增或调整以下文件：

- `backend/open_webui/retrieval/loaders/main.py`
  - PowerPoint 路由入口改造
- `backend/open_webui/retrieval/loaders/powerpoint_markdown.py`
  - 放 `PowerPointMarkdownLoader`
- `backend/open_webui/retrieval/loaders/powerpoint_converter.py`
  - 放 `PowerPointConverter`
- `backend/open_webui/retrieval/loaders/powerpoint_fallback.py`
  - 放 `PowerPointFallbackLoader`
- `ppt_runtime/README.md`
  - 中文离线部署说明

如果实现时发现文件数过多，也可以将 3 个新组件先合并为一个 `powerpoint.py`，但应保留清晰的类边界。

## Loader 选择策略

在 [main.py](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/backend/open_webui/retrieval/loaders/main.py) 中，对 PowerPoint 类型改为新的优先级：

1. PowerPoint 文件统一走 `PowerPointMarkdownLoader`
2. `PowerPointMarkdownLoader` 内部优先 `MarkItDown`
3. 主路径失败再走 fallback

这意味着：

- 不再优先依赖 `UnstructuredPowerPointLoader`
- 不再让 PowerPoint 走当前不稳定的 `unstructured` 默认路径
- 也不依赖外部网络或外部解析服务

## `.ppt` 转换策略

### 工具选择

老 `.ppt` 的本地转换工具统一选 `LibreOffice/soffice`。

原因：

- 这是老 PowerPoint 二进制格式转现代 `.pptx` 最成熟的本地方案之一
- Windows 本地可安装
- 可通过命令行调用
- 不需要新增网络服务

### 转换规则

- 输入文件为解密后的 `.ppt`
- 输出放到临时目录
- 输出文件名与原文件保持可追踪关系
- 转换完成后使用临时 `.pptx` 进入 `MarkItDown`
- 解析结束后删除临时转换文件

### 转换失败处理

遇到以下情况直接视为主路径失败：

- 未找到 `soffice`
- `soffice` 返回非零状态码
- 超时
- 输出 `.pptx` 不存在

如果 fallback 不可用，则前端给出明确错误：

`当前服务器未安装或无法调用 LibreOffice，无法解析 .ppt，请联系管理员安装离线依赖或改传 .pptx。`

## `MarkItDown` 调用策略

### 调用方式

本次不走 CLI 子进程优先方案，而是优先走**Python 库直调**，原因是：

- 更容易跟当前后端直接集成
- 错误捕获更自然
- 少一层命令行转义与编码问题

如果实现中发现库直调能力不足，可退为 CLI 子进程模式，但这不是首选。

### 解析产物

`MarkItDown` 的输出统一视为 Markdown 文本，直接作为：

- `Document.page_content`

并补充基础 metadata，例如：

```json
{
  "source": "example.pptx",
  "content_format": "markdown",
  "parsed_by": "markitdown",
  "original_extension": "pptx"
}
```

如果是 `.ppt` 转换后得到的内容，可额外标记：

```json
{
  "converted_from_ppt": true
}
```

## fallback 策略

### 触发条件

以下任一情况触发 fallback：

- `MarkItDown` 未安装
- `MarkItDown` 调用抛异常
- `MarkItDown` 返回空文本
- `.ppt` 主转换链路完成后 Markdown 为空

### fallback 输出要求

fallback 使用 `python-pptx` 提取：

- 幻灯片标题
- 文本框
- 项目符号
- 可获取到的表格文本

并拼成简单 Markdown，例如：

```md
# Slide 1

## 标题

- 要点 1
- 要点 2

## 备注

...
```

fallback 的目标是：

- 保证文本能进入向量库
- 保证问答可用
- 不追求高保真版式

## 配置设计

本次建议增加一组显式配置，避免把 PowerPoint 解析行为隐含在大而杂的配置里。

建议新增：

- `ENABLE_OFFLINE_PPT_PARSER`
  - 默认 `True`
- `OFFLINE_PPT_PARSER`
  - 默认 `markitdown`
- `PPT_CONVERTER_COMMAND`
  - 默认 `soffice`
- `PPT_CONVERTER_TIMEOUT_SECONDS`
  - 默认 `120`
- `PPT_MARKITDOWN_TIMEOUT_SECONDS`
  - 默认 `120`
- `PPT_FALLBACK_ENABLED`
  - 默认 `True`

这些配置应优先允许通过：

- 环境变量
- `start.py` 默认注入

这样便于内网部署时统一控制。

## 离线依赖策略

### 1. Python 依赖

建议新增一个与 `embedding_model`、`nltk_data` 类似风格的离线说明目录：

- `ppt_runtime/README.md`

说明内容包括：

- 如何在外网下载 `MarkItDown` 相关 wheel
- 如何导入到内网 `vendor/pip` 或离线 wheel 目录
- 如何验证安装成功

### 2. 系统级依赖

`.ppt` 支持依赖本机 `LibreOffice`。

因此 `ppt_runtime/README.md` 还应明确说明：

- Windows 离线安装 `LibreOffice` 的步骤
- 如何把 `soffice.exe` 放入 PATH
- 如何执行自检命令

### 3. 启动时检查

建议在 `start.py` 中增加非阻塞提示：

- 若检测到 `MarkItDown` 缺失，提醒 `.ppt/.pptx` 将退化或失败
- 若检测到 `soffice` 缺失，提醒 `.ppt` 不可用、`.pptx` 仍可继续

这里的原则是：

- 给出明确提示
- 不要因此阻断整站启动

## 错误处理与日志

### 必须新增的日志节点

PowerPoint 解析至少记录以下日志：

- 开始处理 PowerPoint
- 识别到 `.ppt` 或 `.pptx`
- 开始 `.ppt -> .pptx` 转换
- `.ppt` 转换成功 / 失败
- 开始调用 `MarkItDown`
- `MarkItDown` 成功 / 失败
- 开始 fallback
- fallback 成功 / 失败
- 最终文件状态

### 文件状态规则

PowerPoint 文件处理结果只允许落到三种状态：

- `pending`
- `completed`
- `failed`

任何异常都必须显式更新状态，不允许卡在 `pending`。

### 错误信息

建议把可读错误原因写入文件数据或日志，例如：

- `MarkItDown 未安装`
- `LibreOffice 不可用`
- `PowerPoint 转换超时`
- `PowerPoint Markdown 内容为空`

这有助于管理员排查，也便于后续前端展示。

## 与现有链路的兼容性

本方案与以下现有能力兼容：

- 上传解密逻辑不变
- Excel / Word / TXT 不受影响
- embedding 模型配置不变
- 向量库写入逻辑不变
- 聊天问答链路不变

也就是说，本次变更应被视为：

> 在现有系统中新增一条“离线 PowerPoint Markdown 解析能力”，而不是重写文档处理系统。

## 验收标准

### 功能验收

以下场景必须通过：

1. 上传一个已加密的 `.pptx`
   - 解密成功
   - 解析成功
   - 入向量库成功
   - 聊天中可基于其内容问答

2. 上传一个已加密的 `.ppt`
   - 解密成功
   - 本地转换成功
   - 解析成功
   - 入向量库成功
   - 聊天中可基于其内容问答

3. `.pptx` 主解析失败
   - fallback 生效
   - 文件仍可入库

4. 服务器缺少 `LibreOffice`
   - `.ppt` 快速失败
   - 前端不无限转圈
   - 日志明确说明原因

5. 服务器缺少 `MarkItDown`
   - `.pptx` 退化为 fallback 或明确失败
   - 前端不无限转圈

### 稳定性验收

- PowerPoint 处理全流程不出现无限等待
- 每个失败场景都能在日志中定位
- 不影响 Excel / Word / TXT 已有可用能力

### 部署验收

在没有外网的内网服务器上，仅依靠：

- 项目代码
- 离线 Python 包
- 离线安装的 `LibreOffice`

即可完成部署，不依赖在线下载。

## 风险与取舍

### 1. `.ppt` 的根本限制仍然存在

老 `.ppt` 本质上不是现代开放 XML 格式。  
即使我们最终统一让它走 `MarkItDown`，也必须先经过一次本地转换。

这意味着：

- `.ppt` 的可用性上限仍然受 `LibreOffice` 影响
- 无法做到像 `.pptx` 一样纯 Python 库直读

### 2. fallback 不是高保真方案

fallback 只能保障“内容不丢光”，不能保障版式质量。  
因此它是稳定性手段，不是主效果手段。

### 3. 不建议第一阶段同时改动其他文档类型

当前目标是稳住 PowerPoint。  
如果同时把 PDF / 图片 / 外部解析链也一起调整，风险会明显上升。

## 后续实施建议

实施顺序建议如下：

1. 落地 PowerPoint loader 与 converter
2. 补单元测试与集成测试
3. 编写 `ppt_runtime/README.md`
4. 在本地 Windows 环境联调
5. 再同步到公司内网环境验证

本次 spec 完成后，再单独编写 implementation plan，不在当前设计文档中混写施工细节。
