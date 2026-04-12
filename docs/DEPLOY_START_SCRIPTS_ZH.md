# Open WebUI 启动脚本部署说明

这份文档专门说明仓库里的两个启动脚本：

- [start.py](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/start.py)
- [start_prod.py](C:/Users/ArcherWoo/Desktop/open-webui-main/open-webui-main/start_prod.py)

目标是让你在 Windows 和 Linux 上都能比较稳定地启动、停止、排错和做内网访问。

## 1. 两个脚本怎么选

### `start.py`

适合：

- 本地开发
- 临时测试
- 一边改代码一边重启
- 想快速确认前后端能不能起来

特点：

- 会准备 `.venv`
- 会检查并安装前后端依赖
- 会在需要时构建前端
- 适合仓库根目录直接运行

### `start_prod.py`

适合：

- 服务器部署
- 长时间运行
- 需要后台启动
- Windows 上需要注册成服务

特点：

- 默认使用 `.venv-prod`
- 支持 `--detach` 后台启动
- 支持 Windows 服务安装、启动、停止、卸载
- 更偏向“部署运行”而不是“开发调试”

## 2. 一个非常重要的访问规则

脚本默认会绑定：

```text
0.0.0.0:8080
```

这表示“监听所有网卡”，方便本机和局域网访问，但它不是浏览器应该直接打开的地址。

浏览器里应该访问：

```text
http://localhost:8080
```

或者访问脚本启动后打印出来的局域网地址，例如：

```text
http://192.168.1.20:8080
http://172.20.5.9:8080
http://10.0.0.8:8080
```

不要在浏览器里访问：

```text
http://0.0.0.0:8080
```

否则很容易出现 `502` 或打不开页面。

## 3. Windows 部署说明

### 3.1 基础要求

建议准备：

- Python 3.11 或 3.12
- Node.js 18 到 22
- npm

在 PowerShell 中检查：

```powershell
python --version
node --version
npm --version
```

### 3.2 首次启动

进入仓库根目录后执行：

```powershell
python start.py
```

如果你想走更偏生产的方式：

```powershell
python start_prod.py
```

首次运行时，脚本通常会做这些事：

- 检查 Python 版本
- 创建虚拟环境
- 安装后端依赖
- 安装前端依赖
- 构建前端
- 启动 Open WebUI

### 3.3 常用命令

开发启动：

```powershell
python start.py
```

只启动后端：

```powershell
python start.py --backend-only
```

生产启动：

```powershell
python start_prod.py
```

生产后台启动：

```powershell
python start_prod.py --detach
```

只做环境准备，不真正启动：

```powershell
python start_prod.py --prepare-only
```

### 3.4 Windows 服务

安装服务：

```powershell
python start_prod.py --install-service
```

安装后立即启动：

```powershell
python start_prod.py --install-service --start-service
```

启动服务：

```powershell
python start_prod.py --start-service
```

停止服务：

```powershell
python start_prod.py --stop-service
```

卸载服务：

```powershell
python start_prod.py --remove-service
```

如果服务安装失败，优先检查：

- 当前 PowerShell 是否“以管理员身份运行”
- 杀毒软件或安全策略是否阻止了服务创建

### 3.5 防火墙与端口

如果你要让其他内网机器访问服务器，需要放行端口，例如 8080。

查看端口监听：

```powershell
Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue
```

如果你要手动加防火墙规则，可以在管理员 PowerShell 中执行：

```powershell
New-NetFirewallRule -DisplayName "Open WebUI 8080" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8080
```

### 3.6 如何优雅停止

如果你是在前台运行：

```powershell
python start.py
```

或者：

```powershell
python start_prod.py
```

直接按：

```text
Ctrl+C
```

脚本现在会先尝试优雅停止，然后在必要时兜底强制结束，不会再像以前那样直接甩一大段 `KeyboardInterrupt` traceback。

### 3.7 端口是否释放

停止后检查：

```powershell
Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue
```

如果没有输出，通常表示端口已经释放。

## 4. Linux 部署说明

### 4.1 基础要求

建议准备：

- Python 3.11 或 3.12
- Node.js 18 到 22
- npm

检查命令：

```bash
python3 --version
node --version
npm --version
```

### 4.2 首次启动

进入仓库根目录后执行：

```bash
python3 start.py
```

或者生产方式：

```bash
python3 start_prod.py
```

### 4.3 常用命令

开发启动：

```bash
python3 start.py
```

只启动后端：

```bash
python3 start.py --backend-only
```

生产启动：

```bash
python3 start_prod.py
```

后台启动：

```bash
python3 start_prod.py --detach
```

只做准备：

```bash
python3 start_prod.py --prepare-only
```

### 4.4 检查端口与访问

查看 8080 是否在监听：

```bash
ss -ltnp | grep 8080
```

或者：

```bash
netstat -ltnp | grep 8080
```

本机测试：

```bash
curl http://127.0.0.1:8080/
```

内网访问时，用脚本打印出来的局域网地址访问，不要用 `0.0.0.0`。

### 4.5 防火墙

如果使用 `ufw`：

```bash
sudo ufw allow 8080/tcp
```

如果使用 firewalld：

```bash
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

### 4.6 如何优雅停止

前台运行时直接按：

```text
Ctrl+C
```

脚本会先尝试温和停止，如果超时，再兜底结束进程。

如果是后台模式，先找到进程：

```bash
ps -ef | grep start_prod.py
ps -ef | grep uvicorn
```

然后优先使用：

```bash
kill <PID>
```

只有在正常停止不了时，才使用：

```bash
kill -9 <PID>
```

## 5. 启动后你会看到什么

脚本现在会尽量输出中文状态，例如：

```text
[start] 当前使用的基础 Python: ...
[start] 当前使用的虚拟环境 Python: ...
[start] 后端 Python 依赖未发生变化，跳过 pip 安装。
[start] Open WebUI 已启动。
[start] 本机访问地址: http://localhost:8080
[start] 局域网访问地址: http://192.168.1.20:8080
```

这几行里最重要的是最后两类地址：

- `本机访问地址`
- `局域网访问地址`

你在浏览器里优先打开这两个。

## 6. 优雅退出说明

### `Ctrl+C` 之后会发生什么

脚本会尝试按这个顺序处理：

1. 捕获中断信号
2. 输出中文提示
3. 请求子进程停止
4. 等待一段时间
5. 如果还没停，再强制结束
6. 输出“已停止”

### 什么叫优雅关闭

优雅关闭的意思是：

- 尽量让服务自己正常收尾
- 释放端口
- 避免残留僵尸进程
- 尽量不要直接把运行现场打断

### 什么叫超时强制结束

如果脚本发现服务在限定时间内还没退出，就会进入兜底清理。这不是异常，反而是为了防止程序卡住后端口一直被占用。

## 7. 常见故障排查

### 7.1 浏览器打不开，但终端显示已经启动

优先确认你访问的是不是：

```text
http://localhost:8080
```

或者脚本打印出来的局域网地址。

不要访问：

```text
http://0.0.0.0:8080
```

### 7.2 端口被占用

Windows：

```powershell
Get-NetTCPConnection -LocalPort 8080
```

Linux：

```bash
ss -ltnp | grep 8080
```

### 7.3 Python 版本不对

项目优先支持：

- Python 3.11
- Python 3.12

如果你用的是 3.13，脚本会尽量自动切换到可用版本；如果机器上根本没有 3.11 或 3.12，就需要你先安装。

### 7.4 局域网访问不了

重点检查：

- 服务器防火墙是否放行 8080
- 客户端和服务器是否在同一内网
- 访问的是不是脚本打印出来的私网地址
- 路由器或交换机是否做了额外隔离

### 7.5 后台启动后想看日志

如果用了：

```powershell
python start_prod.py --detach
```

或者：

```bash
python3 start_prod.py --detach
```

脚本会打印日志文件路径，优先去看：

- stdout log
- stderr log

## 8. 推荐用法

### 本地开发推荐

```powershell
python start.py
```

或者：

```bash
python3 start.py
```

### 内网服务器推荐

如果只是先跑起来验证：

```powershell
python start_prod.py
```

或者：

```bash
python3 start_prod.py
```

如果希望放到后台长期跑：

```powershell
python start_prod.py --detach
```

或者：

```bash
python3 start_prod.py --detach
```

Windows 上如果要做常驻服务，优先考虑：

```powershell
python start_prod.py --install-service --start-service
```
