# PPT 离线运行时打包目录设计

## 目标

在项目根目录新增一个可以**直接打包成 zip 并带入公司内网**的离线运行时目录，用于支撑 PowerPoint 本地解析链路的部署与验证。

该目录需要满足以下目标：

- 包含 `MarkItDown` 及其 PowerPoint 相关 Python 离线依赖
- 记录 `onnxruntime` 版本变化与原因
- 预留 `LibreOffice` 安装包位置
- 支持 Windows 上自动静默安装 `LibreOffice`
- 提供一键安装、一键校验、一键采集环境信息脚本
- 提供完整中文 README，确保“解压后照着执行脚本即可跑通”

本次设计服务的最终场景是：

> 将 `ppt_offline_runtime/` 整个目录压缩带入公司内网，解压后执行脚本，即可完成 PowerPoint 离线运行时的安装与验证。

## 设计结论

采用**根目录完整离线包目录**方案：

- 根目录新增 `ppt_offline_runtime/`
- 目录中同时承载：
  - Python wheel 包
  - LibreOffice 安装包占位与说明
  - 自动安装脚本
  - 自动校验脚本
  - 环境信息收集脚本
  - 版本与依赖记录
  - 中文部署说明

不复用现有 `vendor/` 作为对外打包入口，也不只提供生成脚本，而是直接把“内网搬运所需内容”收敛到一个独立目录里。

## 适用约束

本方案建立在以下前提上：

- 目标服务器为 `Windows + CPU`
- 可以使用管理员权限执行安装脚本
- 不接受额外起独立解析服务
- 可以接受本机静默安装 `LibreOffice`
- 可以接受项目根目录新增一个较大的离线运行时目录

## 范围

本次覆盖：

- `ppt_offline_runtime/` 目录结构设计
- 离线 Python 包打包策略
- `LibreOffice` 离线安装包放置约定
- 自动静默安装与校验脚本设计
- 版本记录与 hash 记录
- 中文 README 与内网使用流程

本次不覆盖：

- 把 `LibreOffice` 安装包自动从外网下载到仓库
- 把所有文档类型都纳入同一个离线运行时目录
- 替代现有 `vendor/` 体系
- 自动打 Release 或自动上传 GitHub

## 为什么要单独做一个离线运行时目录

当前项目已经存在多种“内网补齐资源”的目录或机制：

- `embedding_model/`
- `nltk_data/`
- `pyodide_runtime/`
- `vendor/`

但它们的职责各不相同，且不完全满足这次的目标：

- `embedding_model/` 和 `nltk_data/` 更像“资源目录”
- `vendor/` 更偏项目内部依赖缓存体系
- `pyodide_runtime/` 更偏前端运行时资产

而这次需求的核心是：

- 面向公司内网搬运
- 可直接压缩打包
- 可单独解释与使用
- 附带一键脚本

因此需要一个独立、完整、可读性强的离线运行时目录。

## 目录设计

最终目录结构建议如下：

```text
ppt_offline_runtime/
├─ README.md
├─ VERSION_MANIFEST.md
├─ wheels/
│  ├─ markitdown-*.whl
│  ├─ onnxruntime-1.20.1-*.whl
│  ├─ magika-*.whl
│  ├─ markdownify-*.whl
│  └─ 其他 markitdown[pptx] 所需依赖
├─ libreoffice/
│  ├─ README.md
│  └─ 把 LibreOffice 安装包放在这里
├─ scripts/
│  ├─ install_offline_runtime.ps1
│  ├─ verify_offline_runtime.ps1
│  ├─ collect_runtime_info.ps1
│  └─ helpers.ps1
├─ records/
│  ├─ dependency-lock.txt
│  ├─ hashes.txt
│  └─ runtime-notes.md
└─ logs/
   └─ .gitkeep
```

### 各目录职责

#### `wheels/`

职责：

- 存放离线 Python wheel
- 安装脚本只从这里安装，不走网络

要求：

- 至少包含 `markitdown[pptx]` 的关键依赖闭包
- 明确锁定 `onnxruntime==1.20.1`

#### `libreoffice/`

职责：

- 存放管理员后续手工放入的 `LibreOffice` 安装包
- 不要求仓库一开始就自带安装包

要求：

- README 明确写“把安装包放这里”
- 安装脚本只从这里查找安装包

#### `scripts/`

职责：

- 承载安装、校验、信息收集脚本
- 让内网同事通过固定脚本完成部署

#### `records/`

职责：

- 记录依赖版本
- 记录 hash
- 记录版本调整原因

#### `logs/`

职责：

- 存放安装日志与验证日志
- 便于管理员排查问题

## 离线 wheel 策略

### 目标

将 `MarkItDown` PowerPoint 解析链所需的 Python 包显式下载到本地目录，并作为“可搬运资产”一并打包。

### 关键包

至少包括：

- `markitdown`
- `magika`
- `markdownify`
- `onnxruntime==1.20.1`
- `markitdown[pptx]` 拉下来的其他闭包依赖

### `onnxruntime` 版本锁定

本次必须明确记录：

- 原本本地环境中存在 `onnxruntime 1.24.3`
- 安装 `markitdown 0.1.5` 时，由于其依赖的 `magika 0.6.3` 约束，`onnxruntime` 被调整为 `1.20.1`

这一点必须在以下位置都有记录：

- `VERSION_MANIFEST.md`
- `records/runtime-notes.md`
- `README.md`

### 设计原则

- 以“当前真实验证通过的组合”为准
- 不追求依赖版本最新
- 优先保证可复现与可搬运

## `LibreOffice` 安装包策略

### 设计原则

项目负责：

- 预留目录
- 预留说明
- 编写静默安装脚本
- 编写校验脚本

项目不负责：

- 自动从外网下载 `LibreOffice`

原因：

- 安装包体积大
- 版本与下载地址可能变化
- 带上二进制安装包会使仓库膨胀过快

因此，最终模式是：

1. 管理员在外网机器下载 `LibreOffice`
2. 手动放入 `ppt_offline_runtime/libreoffice/`
3. 将整个 `ppt_offline_runtime/` 目录一起压缩带入内网
4. 在内网执行脚本自动静默安装

## 脚本设计

### 1. `install_offline_runtime.ps1`

职责：

- 检查是否在项目根目录执行
- 检查 `.venv` 是否存在
- 离线安装 `wheels/` 中的 Python 包
- 检查 `libreoffice/` 中是否存在安装包
- 若存在安装包且当前为管理员权限，则自动静默安装 `LibreOffice`
- 尝试刷新当前会话中对 `soffice` 的定位
- 把安装过程写入日志

必须具备的行为：

- 支持重复执行
- Python 部分允许覆盖已有版本
- 日志清晰
- 安装失败时退出码非零

### 2. `verify_offline_runtime.ps1`

职责：

- 校验 `markitdown` 是否可导入
- 校验 `onnxruntime` 实际版本
- 校验 `soffice` 是否存在
- 生成一个最小真实 `pptx`
- 用 `MarkItDown` 实际跑一次
- 用项目内 `PowerPointMarkdownLoader` 再跑一次
- 输出结果摘要与日志路径

这是最关键的“带进内网后一键验收脚本”。

### 3. `collect_runtime_info.ps1`

职责：

- 收集当前机器上的：
  - Python 路径
  - `.venv` 路径
  - `markitdown` 版本
  - `onnxruntime` 版本
  - `soffice` 路径
  - PowerPoint loader 导入状态
- 输出到日志文件中

适用于：

- 问题排查
- 内网环境采集
- 给 IT 或管理员回传状态

### 4. `helpers.ps1`

职责：

- 放公共函数
- 避免 3 个脚本各自复制相同的日志、权限、路径判断逻辑

## 自动静默安装 `LibreOffice`

### 设计目标

如果管理员已经将安装包放入 `ppt_offline_runtime/libreoffice/`，则安装脚本应自动尝试静默安装。

### 行为规则

安装脚本需支持以下策略：

- 优先识别 `.msi`
- 次优识别常见 `.exe`
- 如果目录内无安装包：
  - 不阻塞 Python 离线依赖安装
  - 明确提示 `.ppt` 仍不可用
- 如果安装包类型未知：
  - 明确报错

### 权限要求

静默安装前必须检查管理员权限。

如果不是管理员：

- 不强行继续安装 `LibreOffice`
- 明确提示“需要管理员权限”
- Python wheel 仍可继续安装

## 版本与记录设计

### `VERSION_MANIFEST.md`

用于记录本离线包当前收敛出来的版本组合，例如：

- `markitdown==0.1.5`
- `magika==0.6.3`
- `onnxruntime==1.20.1`

同时说明：

- 这是本地验证通过的组合
- 不要随意单独升级其中任一项

### `records/dependency-lock.txt`

记录离线 wheel 文件名清单，便于核对“包是否带齐”。

### `records/hashes.txt`

记录 wheel 文件 hash，用于内网核验。

### `records/runtime-notes.md`

用中文解释：

- 为什么要加这个离线目录
- 为什么 `onnxruntime` 版本变了
- `.pptx` 与 `.ppt` 分别依赖什么
- `.ppt` 为什么还需要 `LibreOffice`

## README 设计

`ppt_offline_runtime/README.md` 必须做到：

- 中文
- 傻瓜式
- 一步一步
- 让非开发同事也能照着做

至少要包括以下章节：

1. 这个目录是干什么的
2. 你需要准备什么
3. 外网机器怎么补齐 wheel
4. `LibreOffice` 安装包放哪里
5. 内网机器怎么解压和执行
6. 怎么看安装是否成功
7. 怎么看 `.pptx` 和 `.ppt` 是否已经可用
8. 常见错误与排查

## 内网使用流程

最终推荐流程应固定为：

1. 在外网机器补齐 `wheels/`
2. 将 `LibreOffice` 安装包放入 `libreoffice/`
3. 将整个 `ppt_offline_runtime/` 压缩打包
4. 带入公司内网并解压
5. 以管理员身份运行 `scripts/install_offline_runtime.ps1`
6. 运行 `scripts/verify_offline_runtime.ps1`
7. 通过后再启动 `python start.py`

## 验收标准

### 打包验收

- `ppt_offline_runtime/` 目录结构完整
- wheel 包存在
- 记录文件存在
- 脚本存在
- `libreoffice/` 目录存在并有说明

### 安装验收

在一台全新的 `Windows + CPU` 机器上：

- 能离线安装 `markitdown`
- 能把 `onnxruntime` 调整到预期版本
- 能静默安装 `LibreOffice`

### 验证验收

执行 `verify_offline_runtime.ps1` 后应能确认：

- `import markitdown` 成功
- `onnxruntime` 版本符合预期
- `soffice` 可执行
- 真实 `.pptx` 可被 `MarkItDown` 解析
- 真实 `.pptx` 可被项目内 `PowerPointMarkdownLoader` 解析

## 风险与取舍

### 1. 仓库体积会增加

这是方案 1 的必然代价。  
但它换来的是：

- 搬运简单
- 目录职责清晰
- 不需要到处拼材料

### 2. `LibreOffice` 安装包不直接纳入仓库默认提交

目录会预留，但安装包通常由管理员后放。  
这是在“完整打包体验”和“仓库体积/合规性”之间做的平衡。

### 3. 运行时组合要锁定

一旦验证通过，不建议单独替换 wheel 版本。  
否则很容易出现“脚本还在，但版本组合不再可复现”的问题。

## 后续实施建议

建议按以下顺序实施：

1. 新增 `ppt_offline_runtime/` 目录结构
2. 下载并放入 wheel
3. 生成版本与 hash 记录
4. 编写安装与校验脚本
5. 做一次本地真实安装/验证
6. 再打包给公司内网使用

本次 spec 完成后，应继续单独编写 implementation plan，再开始真正落地目录与脚本。
