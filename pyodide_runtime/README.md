# Pyodide 内网离线导入说明

这个目录是给 Pyodide 内网离线部署准备的中文说明入口。

先说结论：

- `nltk_data/`、`embedding_model/` 那种方案，是“后端运行时按目录读取”
- `pyodide` 不是这一类
- `pyodide` 是前端 npm 构建阶段依赖，同时还带浏览器运行时静态资源

所以它不能只靠“根目录放一个文件夹”就解决。

真正需要恢复到仓库里的，是这两个目录：

- `vendor/npm/`
- `static/pyodide/`

## 这个目录是干什么的

`pyodide_runtime/` 主要负责两件事：

1. 放中文操作说明
2. 临时存放你从外网带进来的离线包或记录文件

它本身不是实际生效位置。

实际生效的离线资源，最终还是要放回：

- `vendor/npm/`
- `static/pyodide/`

## 什么时候你会需要它

如果你在公司内网执行：

```powershell
python start.py
```

然后在前端依赖安装或构建阶段看到类似报错：

- `Cannot find package 'pyodide'`
- `ERR_MODULE_NOT_FOUND: pyodide`
- `prepare-pyodide.js` 下载失败

那基本就是这块没有补齐。

## 为什么不能只放一个目录就完事

因为 Pyodide 涉及两层东西：

### 1. npm 构建期依赖

用于让前端构建脚本能找到：

- `pyodide` npm 包

这部分要走：

- `vendor/npm/`

### 2. 浏览器运行时静态资源

用于网页加载时实际访问：

- `pyodide.js`
- `.wasm`
- Python 标准库压缩包
- Micropip 等运行时资源

这部分要走：

- `static/pyodide/`

所以缺一不可。

## 你在内网应该怎么做

### 第 1 步：在外网机器准备资源

在能联网的机器上，先把 npm 依赖和 Pyodide 运行时资源准备好。

通常你会得到两部分结果：

- 一份可复用的 npm 缓存或 vendor 目录
- 一份完整的 `static/pyodide/` 资源目录

### 第 2 步：带进公司内网

建议把这两部分一起打包带进去。

### 第 3 步：恢复到项目实际位置

最终你要把资源恢复到：

- `vendor/npm/`
- `static/pyodide/`

不是停留在 `pyodide_runtime/` 目录里。

## 可不可以手动复制粘贴

可以。

如果你已经把外网准备好的资源解压出来了，完全可以直接手动复制到：

- `vendor/npm/`
- `static/pyodide/`

只要目录结构对，效果和脚本恢复是一样的。

## 这和 start.py 的关系

`python start.py` 在构建前端时，会依赖 npm 环境和 Pyodide 相关脚本。

如果：

- `vendor/npm/` 不完整
- 或者 `static/pyodide/` 缺失

就会在构建阶段失败。

## 你可以怎么长期维护

以后如果 Pyodide 或前端依赖有明显升级，建议在外网机器重新做一轮准备，然后再带新的离线包进内网替换。

一个常见流程是：

```powershell
npm ci --cache .\vendor\npm --prefer-offline
$env:OPEN_WEBUI_ALLOW_PYODIDE_DOWNLOAD='true'
npm run pyodide:fetch
```

然后把新的离线资源重新打包带进内网。

## 最后再强调一次

这里正确的理解是：

- `pyodide_runtime/` 是说明入口
- `vendor/npm/` 解决 npm 构建依赖
- `static/pyodide/` 解决浏览器运行时资源

只有这两部分都补齐，Pyodide 才算真正恢复。
