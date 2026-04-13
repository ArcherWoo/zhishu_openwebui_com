# Open WebUI Vendor 预下载与内网部署手册

## 目标

这个流程用于公司内网部署场景：

- 内网机器只能访问公司镜像源
- 有些包公司镜像源没有，需要在外网机器手工补
- 希望 `start.py` 安装依赖时优先使用项目根目录下的本地 vendor 缓存

本项目已经支持：

- 预下载后端 Python 依赖到 `vendor/python`
- 预缓存前端 npm 依赖到 `vendor/npm`
- 生成报告，列出哪些包成功、哪些包失败、哪些需要手工补
- `python start.py` 安装时优先从 `vendor/python` 和 `vendor/npm` 安装
- 如果本地 vendor 不完整，则自动回退到当前环境配置好的镜像源

## 目录说明

- `vendor/python`
  说明：后端 Python 依赖缓存目录
- `vendor/npm`
  说明：前端 npm 缓存目录
- `vendor/report.json`
  说明：机器可读报告
- `vendor/report.md`
  说明：人工查看报告，包含手工补包命令

## 使用顺序

### 1. 先做只校验，不下载

先确认当前公司镜像源到底能覆盖多少。

```bash
python prefetch_vendor_deps.py --dry-run
```

这一步会：

- 读取当前环境里的 `pip` 镜像和 `npm registry`
- 尽量校验 Python / npm 依赖是否能从当前源获取
- 不真正下载依赖包
- 输出报告到 `vendor/report.json` 和 `vendor/report.md`

如果返回码为 `0`，说明当前校验结果比较完整。

如果返回码非 `0`，说明还有缺失项，需要看报告继续处理。

### 2. 再执行真实预下载

```bash
python prefetch_vendor_deps.py
```

这一步会：

- 把 Python 依赖尽量下载到 `vendor/python`
- 把 npm 依赖尽量缓存到 `vendor/npm`
- 遇到某个包失败时继续尝试后面的包
- 最后再做一次整体完整性校验
- 更新 `vendor/report.json` 和 `vendor/report.md`

## 报告怎么看

重点看 `vendor/report.md`。

里面主要有几块：

- `Python Missing`
  说明：当前源里连直接 requirement 都拿不到
- `Python Bundle Failures`
  说明：直接 requirement 可能存在，但它的依赖链不完整
- `NPM Missing`
  说明：对应的 `package@version` 没能进本地 npm cache
- `手工补包命令`
  说明：建议你在外网机器上执行的补包命令
- `Offline vendor validation complete`
  说明：当前 vendor 目录是否已经足够支持离线/近离线安装

## 外网补包建议

### Python

如果报告里出现类似：

```bash
python -m pip download --dest vendor/python "fastapi==0.1.0"
```

你可以在外网机器上进入项目根目录后执行对应命令，把下载好的文件放进 `vendor/python`。

建议：

- 外网机器尽量使用与部署机相同的大版本 Python
- 补包后把整个 `vendor/python` 带回内网机器

### npm

如果报告里出现类似：

```bash
npm cache add "react@18.3.1" --cache vendor/npm
```

你可以在外网机器项目根目录执行对应命令，把 npm cache 内容写进 `vendor/npm`，然后再把整个 `vendor/npm` 带回内网机器。

建议：

- 外网和内网尽量使用相近版本的 npm
- 不要只拷单个文件，优先整目录复制 `vendor/npm`

## 内网部署

当 `vendor` 目录准备好之后，直接执行：

```bash
python start.py
```

当前 `start.py` 的行为是：

- Python 先尝试只从 `vendor/python` 安装
- 如果本地 vendor 不完整，则回退到当前镜像源继续安装
- npm 先尝试只从 `vendor/npm` 离线安装
- 如果本地 vendor 不完整，则回退到当前镜像源并优先使用缓存继续安装

## 推荐工作流

### 场景 A：先在公司内网机器上跑

```bash
python prefetch_vendor_deps.py --dry-run
python prefetch_vendor_deps.py
python start.py
```

适合你先看看公司镜像能搞定多少。

### 场景 B：先在外网机器补齐，再带回内网

```bash
python prefetch_vendor_deps.py --dry-run
python prefetch_vendor_deps.py
```

然后：

- 按 `vendor/report.md` 里的手工补包命令补齐缺失项
- 把整个 `vendor/` 目录复制回内网机器
- 在内网机器上执行：

```bash
python start.py
```

## 常见问题

### 1. 为什么 dry-run 也会生成 vendor 目录？

为了统一输出路径和报告位置，脚本会创建 vendor 目录，但 dry-run 不会主动把依赖包写满进去。

### 2. 为什么报告里 direct requirement 成功了，但整体校验还是失败？

这通常说明：

- 直接包存在
- 但它依赖的某个传递依赖在当前源里缺失

这时重点看：

- `Python Bundle Failures`
- `NPM Missing`
- `Offline vendor validation error`

### 3. 为什么 start.py 还会联网？

因为现在的策略是：

- 本地 vendor 优先
- vendor 不完整时自动回退到当前镜像源

如果你想改成“绝对离线，不允许任何回退”，可以再单独改成严格离线模式。

## 建议

- 先执行 `python prefetch_vendor_deps.py --dry-run`
- 再执行 `python prefetch_vendor_deps.py`
- 看 `vendor/report.md`
- 把缺失包在外网补齐
- 最后在内网机器执行 `python start.py`
