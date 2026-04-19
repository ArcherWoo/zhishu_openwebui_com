# Pyodide 内网离线导入说明

这个目录是给 **Pyodide 内网离线部署** 准备的中文说明入口。

先说结论：

- `nltk_data/` 和 `embedding_model/` 那种方案，是“后端运行时按目录读取”
- `pyodide` 不是这一类，它是 **前端 npm 构建阶段依赖**
- 所以它不能只靠“根目录放个文件夹”就解决第一次构建失败
- 真正需要恢复到仓库里的，是下面两个目录：
  - `vendor/npm/`
  - `static/pyodide/`

也就是说：

- 这个 `pyodide_runtime/` 目录主要负责放中文说明，必要时你也可以把 zip 临时放这里
- 实际生效的离线资源，还是要通过脚本恢复到 `vendor/npm/` 和 `static/pyodide/`

## 一、什么时候需要它

如果你在公司内网执行：

```powershell
python start.py
```

然后在一开始的前端依赖安装或构建阶段看到类似问题：

- `Cannot find package 'pyodide'`
- `npm ci` 失败
- `npm run build` 失败
- `node scripts/prepare-pyodide.js` 失败

那就说明当前机器缺少 Pyodide 离线资产，需要走下面这套流程。

## 二、外网机器怎么准备

这一步在能正常访问外网 npm 的机器上做。

### 1. 先进入项目根目录

```powershell
cd 你的项目目录
```

### 2. 先把前端 npm 依赖装好，并填充本地缓存

```powershell
npm ci --cache .\vendor\npm --prefer-offline
```

说明：

- 这里不是只下 `pyodide`
- 而是把 **前端整套 npm 构建所需缓存** 都放进 `vendor/npm`
- 这样你带进内网时，`npm ci` 才更稳

### 3. 再准备 Pyodide 浏览器运行时资源

```powershell
$env:OPEN_WEBUI_ALLOW_PYODIDE_DOWNLOAD='true'
npm run pyodide:fetch
```

这一步会把 Pyodide 相关文件和离线 wheel 准备到：

- `static/pyodide/`

说明：

- 现在 `pyodide:fetch` 默认不会自动联网下载
- 只有显式设置 `OPEN_WEBUI_ALLOW_PYODIDE_DOWNLOAD=true` 时，才会执行下载和锁文件生成
- 这样做是为了避免内网环境里误触发外网请求

### 4. 打包成 Release 附件 zip

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-pyodide-release.ps1 -OverwriteLatest
```

执行后会生成：

- `dist/releases/pyodide-offline-runtime-latest.zip`
- `dist/releases/pyodide-offline-runtime-latest.sha256`
- `dist/releases/pyodide-offline-runtime-latest.txt`

## 三、怎么上传到 GitHub

推荐做法是：

1. 把代码正常提交到 GitHub 仓库
2. 不要把 `vendor/` 和 `static/pyodide/` 直接提交进 git
3. 把上一步生成的 zip 作为 **GitHub Release 附件** 上传

这样仓库本身不会特别重，但你在内网仍然能拿到完整离线包。

## 四、内网机器怎么恢复

### 1. 把 zip 放进项目里

你可以放在任意位置，常见两种：

- `.\pyodide_runtime\pyodide-offline-runtime-latest.zip`
- `.\dist\releases\pyodide-offline-runtime-latest.zip`

### 2. 执行恢复脚本

如果 zip 放在 `pyodide_runtime/` 里：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restore-pyodide-release.ps1 -ArchivePath .\pyodide_runtime\pyodide-offline-runtime-latest.zip
```

如果 zip 放在 `dist/releases/` 里：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restore-pyodide-release.ps1 -ArchivePath .\dist\releases\pyodide-offline-runtime-latest.zip
```

恢复完成后，仓库里应该出现并可正常使用：

- `vendor/npm/`
- `static/pyodide/`

### 3. 启动项目

```powershell
python start.py
```

## 五、恢复后检查什么

至少检查下面两项：

### 1. npm 缓存目录是否存在

```powershell
dir .\vendor\npm
```

### 2. Pyodide 锁文件是否存在

```powershell
dir .\static\pyodide\pyodide-lock.json
```

如果这两项都有，再启动 `python start.py`，一般就能过掉之前那个 `pyodide` 缺失问题。

## 六、为什么不是直接把 pyodide 放根目录

因为它和 `nltk_data/` 的性质不一样。

`nltk_data/`：

- 后端运行时读取
- 只要路径对，程序启动后能找到就行

`pyodide`：

- 前端构建期依赖
- `npm ci` 先得能装出来
- `scripts/prepare-pyodide.js` 还要继续读取 `node_modules/pyodide`

所以这里正确的处理方式一定是：

- 用 `vendor/npm` 解决 npm 构建期依赖
- 用 `static/pyodide` 解决浏览器运行时资源

## 七、建议你长期这么做

以后每次 Pyodide 或前端依赖有明显升级时，就在外网机器重新跑一遍：

```powershell
npm ci --cache .\vendor\npm --prefer-offline
$env:OPEN_WEBUI_ALLOW_PYODIDE_DOWNLOAD='true'
npm run pyodide:fetch
powershell -ExecutionPolicy Bypass -File .\scripts\package-pyodide-release.ps1 -OverwriteLatest
```

然后把新的 zip 替换掉旧的 Release 附件即可。
