# scripts 目录说明

这个目录用来放项目运维、构建准备、排障辅助之类的脚本。

目前包含下面几个脚本。

## 1. cleanup-root-artifacts.ps1

用途：

- 整理项目根目录里历史遗留的日志文件
- 把散落在根目录的日志归档到 `logs/root-archive/` 下面
- 尝试清理常见临时目录和缓存目录

适合什么时候用：

- 根目录被各种 `*.log`、`tmp-*`、缓存目录弄得很乱的时候
- 做完一轮排障、联调、验证之后，想把工作区收拾干净的时候

推荐先预览，再正式执行。

预览：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup-root-artifacts.ps1 -WhatIf
```

正式执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup-root-artifacts.ps1
```

当前脚本会处理这些内容：

- 历史日志归档
  - `debug-*.log`
  - `service-install-test*.log`
  - `smoke-start*.log`
  - `start-prod-detach-test*.log`
  - `start-prod-test*.log`
  - `start-test*.log`
  - `verify-*.log`
  - `tmp-build-warnings*.log`
  - `tmp-shutdown-repro.log`
  - `tmp-open-webui*.log`
- 常见临时目录清理
  - `__pycache__`
  - `.tmp-py`
  - `.tmp-pytest`
  - `tmp-runtime-temp`
  - `tmp-test-artifacts`
  - `tmp-upload-decryption-smoke`
  - `.tmp-probe-root`

注意事项：

- 脚本只处理仓库根目录下的明确目标，不会去碰源码目录、依赖目录
- `.start-state.json` 是启动脚本在用的状态文件，脚本不会移动它
- 如果某些目录被 Windows 权限或进程占用锁住，脚本会报告失败，但不会误删别的内容

## 2. package-nltk-data-release.ps1

用途：

- 把根目录下的 `nltk_data/` 打成适合上传到 GitHub Release 的附件压缩包
- 同时生成 `.sha256` 校验文件和一个简短说明文件

适合什么时候用：

- 你不想把 `nltk_data/` 这类大目录直接提交进主仓库
- 你想走“代码进 git，资源走 Release 附件”这条方案

常用命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-nltk-data-release.ps1
```

如果你想手动带一个版本号：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-nltk-data-release.ps1 -Version v1
```

如果你想固定覆盖一个最新包文件名：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-nltk-data-release.ps1 -OverwriteLatest
```

输出位置：

- `dist/releases/*.zip`
- `dist/releases/*.sha256`
- `dist/releases/*.txt`

注意事项：

- 这个脚本不会修改 `nltk_data/` 原目录内容
- 打出来的 zip 是给 GitHub Release 附件用的，不建议再提交进主仓库

## 3. generate-sbom.sh

用途：

- 生成软件物料清单（SBOM）相关内容

说明：

- 这是一个 shell 脚本，更适合在带 Bash 的环境里执行
- 如果后续你要在 Windows 下长期使用它，建议再补一份对应的 PowerShell 包装脚本

## 4. prepare-pyodide.js

用途：

- 准备 Pyodide 相关资源

说明：

- 这是一个 Node.js 脚本
- 执行前请确认本机 Node 环境可用，并且项目依赖已安装

## 5. package-pyodide-release.ps1

用途：

- 把 `vendor/npm/` 和 `static/pyodide/` 一起打成一个适合上传到 GitHub Release 的 zip
- 解决公司内网里 npm 源缺少 `pyodide` 时，无法顺利 `python start.py` 的问题

为什么不是只打包 `static/pyodide/`：

- 因为 `pyodide` 报错虽然最显眼，但真正先失败的往往是 `npm ci`
- 所以要把前端 npm 离线缓存 `vendor/npm/` 一起带上

常用命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-pyodide-release.ps1
```

如果你想固定覆盖一个 latest 包名：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-pyodide-release.ps1 -OverwriteLatest
```

输出位置：

- `dist/releases/pyodide-offline-runtime-*.zip`
- `dist/releases/pyodide-offline-runtime-*.sha256`
- `dist/releases/pyodide-offline-runtime-*.txt`

## 6. restore-pyodide-release.ps1

用途：

- 把外网打好的 Pyodide 离线 zip 恢复到当前仓库
- 目标目录是：
  - `vendor/npm/`
  - `static/pyodide/`

常用命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restore-pyodide-release.ps1 -ArchivePath .\pyodide_runtime\pyodide-offline-runtime-latest.zip
```

恢复完成后：

- 就可以继续执行 `python start.py`
- 如果 `start.py` 里提示缺少 Pyodide 离线资源，也会引导到这个脚本和 `pyodide_runtime/README.md`

## 建议

如果后面这个目录继续增加脚本，建议每加一个脚本就顺手把下面三件事补上：

- 在这个 README 里补一段用途说明
- 写清楚运行命令
- 写清楚它会改哪些文件、哪些目录
