# Local Repo MCP 使用教程

[简体中文](USAGE.zh-CN.md) | [English](USAGE.md)

本文档说明安装、首次配置、STDIO、OpenAI Secure MCP Tunnel、Streamable HTTP、日志、测试和常见故障排查。

## 1. 环境准备

开始前需要准备：

- Python 3.11 或更高版本。
- `PATH` 中可以找到 Git。
- 一个允许 Local Repo MCP 暴露给客户端的本地 Git 工作区。
- 只有使用 OpenAI Secure MCP Tunnel 时才需要 `tunnel-client`。

检查基础命令：

```bash
python --version
git --version
```

目标仓库必须通过以下检查：

```bash
git -C /path/to/repository rev-parse --is-inside-work-tree
```

## 2. 从源码目录启动

### Windows

在项目根目录执行：

```powershell
start_gui.bat
```

### Linux/macOS

在项目根目录执行：

```bash
chmod +x start_gui.sh
./start_gui.sh
```

无图形界面时使用交互式命令行：

```bash
chmod +x start_cli.sh
./start_cli.sh
```

启动流程会创建 `.venv`、安装依赖，并在 `requirements.txt` 发生变化时重新同步依赖。

## 3. 安装包方式启动

安装并启动 GUI：

```bash
pip install .
local-repo-mcp-gui
```

无桌面环境：

```bash
local-repo-mcp-cli
```

MCP Server 命令入口为：

```bash
local-repo-mcp
```

源码模式和安装模式都使用 `mcp_app.launcher`。

## 4. 首次配置 GUI

打开**首页**，依次完成：

1. 选择目标 Git 仓库。
2. 选择权限模式。
3. 选择传输方式。
4. 默认限制不合适时，展开高级设置进行调整。
5. 根据传输方式执行连接或启动。

需要执行操作时，GUI 会自动保存配置。仓库路径只有在真实存在、属于目录并且位于 Git 工作区内时才会通过校验。

## 5. 选择权限模式

### `read`

只用于查看，允许：

- 文件列表；
- UTF-8 文本读取；
- 固定字符串检索；
- 过滤后的 Git 状态；
- 过滤后的 Git Diff。

### `write`

包含全部读取能力，并允许调用 `repo_apply_patch`。

写入只接受经过校验的统一文本 Patch。敏感路径、不支持的 Patch 类型、超限输入、目标文件已有冲突修改和疑似凭证内容会被拒绝。

### `test`

包含读取和写入能力，并允许调用 `repo_run_test`。

Test 模式只运行固定注册的 test/build/lint/check 命令；支持单命令和最多 8 个命令的有界顺序批量，整批会在首个命令启动前完成白名单校验。仓库代码仍以当前操作系统用户权限执行，该模式不是沙箱。

## 6. 使用 STDIO

当 MCP 客户端可以自行启动子进程时，推荐使用 STDIO。

### 在 GUI 中验证 STDIO

1. 在首页选择 **STDIO**。
2. 选择仓库和权限模式。
3. 点击**连接**。
4. 等待真实连接测试完成。

测试过程包括：

- MCP initialize；
- 工具发现；
- 执行 `repo_git_status`；
- 核对实际仓库身份与配置仓库是否一致。

STDIO 是按需启动的。连接测试结束后，GUI 不会保留一个常驻 STDIO Server 进程。

### 复制客户端配置

打开 **MCP Server**，展开**客户端配置**，将生成的 JSON 复制到需要启动 Local Repo MCP 的客户端中。

生成的配置包含：

- 当前 Python 可执行文件；
- 打包后的 Launcher 模块；
- 配置的仓库根目录；
- 选定权限模式；
- 输入输出限制；
- MCP Runtime 和审计日志路径。

修改客户端配置后，需要重启或重新加载 MCP 客户端。

## 7. 使用 OpenAI Secure MCP Tunnel

Secure MCP Tunnel 是可选功能。需要单独安装 `tunnel-client`，并准备控制面提供的 Tunnel ID 和 Runtime API Key。

自动 Profile 初始化主要面向 STDIO。

### 配置 Tunnel 页面

1. 保持 Local Repo MCP 传输方式为 **STDIO**。
2. 打开 **ChatGPT 连接**。
3. 将 **Tunnel Client** 设置为 `tunnel-client` 或其完整路径。
4. 设置 Profile 名称，例如 `local-repo`。
5. 输入 Tunnel ID。
6. 输入 Runtime API Key。
7. 需要时设置明确的 Profile 文件路径。

### 初始化并启动

按照以下顺序执行：

1. **检测**：检查可执行文件和已有 Profile。
2. **初始化**：创建 STDIO Tunnel Profile。
3. **诊断**：验证 Profile 和运行配置。
4. **启动 Tunnel**：执行 `tunnel-client run --profile <profile>`。

Runtime API Key 只保存在进程内存中，不会写入 Local Repo MCP 的普通配置文件。

源码位置或 Python 路径变化后，**检测**功能可以修复已识别的 Local Repo MCP 启动命令。修改前会创建 Profile 备份。

手工配置 HTTP Tunnel 时，需要先启动 Streamable HTTP Server，并确保 Tunnel 转发 Bearer 请求头。自动 HTTP Profile 初始化被明确禁用。

## 8. 使用本地 Streamable HTTP

当客户端需要连接常驻端点，而不是自己启动 STDIO 子进程时，使用 Streamable HTTP。

### 推荐本机配置

```text
主机：127.0.0.1
端口：8000
路径：/mcp
允许的 Host：127.0.0.1:*,localhost:*
允许的 Origin：http://127.0.0.1:*,http://localhost:*
```

### 启动并验证

1. 选择 **Streamable HTTP**。
2. 除非确实需要远程访问，否则保持环回地址。
3. 生成或输入 Bearer Token。
4. 点击**启动 HTTP**。
5. 等待就绪检查通过。
6. 点击**连接**，通过 HTTP 执行 MCP initialize 和仓库身份验证。
7. 打开 **MCP Server**，复制生成的客户端配置。

客户端必须发送：

```text
Authorization: Bearer <LOCAL_REPO_MCP_TOKEN>
```

即使只监听本机，Bearer 认证也仍然是强制要求。

## 9. 使用远程 Streamable HTTP

不要将明文 Local Repo MCP HTTP 直接暴露到不可信网络。

必须选择以下一种模式：

### 原生 TLS

配置：

```text
HTTP_TLS_CERTFILE=/path/to/server.crt
HTTP_TLS_KEYFILE=/path/to/server.key
```

可选双向 TLS：

```text
HTTP_TLS_CLIENT_CA=/path/to/client-ca.crt
```

### 可信 TLS 反向代理

配置：

```text
HTTP_TLS_TERMINATED_PROXY=true
HTTP_PUBLIC_URL=https://mcp.example.com/mcp
HTTP_PROXY_TRUSTED_IPS=10.0.0.0/8
```

反向代理必须终止 HTTPS、保留 MCP 路径和 Authorization 请求头、禁止外部直接访问后端，并且代理来源地址必须属于允许范围。

非本机监听必须使用原生 TLS 或可信代理模式。使用 `0.0.0.0` 等通配监听时，还必须配置与 `HTTP_PATH` 路径一致的 HTTPS `HTTP_PUBLIC_URL`。

完整的服务器、systemd、容器和 Kubernetes 示例见[部署指南](DEPLOYMENT.md)。

## 10. 使用 MCP 工具

典型读取流程：

1. `repo_git_status`
2. `repo_list_files`
3. `repo_search_code`
4. `repo_read_file`
5. `repo_git_diff`

典型写入流程：

1. 读取当前文件并检查 Git 状态；
2. 准备一个统一文本 Patch；
3. 调用 `repo_apply_patch`；
4. 检查返回的 Diff；
5. 再次调用 `repo_git_status` 和 `repo_git_diff`。

典型测试流程：

1. 切换到 `test` 模式；
2. 检查当前仓库修改；
3. 单命令使用允许的 `command_key`；批量验证使用 `command_keys`，并按需设置 `stop_on_failure`；
4. 检查每个命令返回的 `status`、`exit_code`、stdout、stderr、耗时和输出截断标记。

Local Repo MCP 不会自动推送修改。本地 commit 仅在 GUI / `ALLOW_GIT_COMMIT` 显式开启时可用。

## 11. 使用日志中心

打开**日志**页面，可以查看：

- **MCP**：Server 生命周期、连接测试、HTTP 进程输出、工具事件以及白名单命令开始/结束状态；
- **Tunnel**：Tunnel 检测、初始化、诊断、启动、停止和进程输出；
- **审计**：仓库操作和执行结果；
- **安全事件**：认证拒绝和权限拒绝等事件。

日志中心支持：

- 实时刷新；
- 关键词检索；
- 日志级别过滤；
- 易读事件摘要；
- 原始 JSON 详情；
- 复制摘要或原始记录。

常见 Bearer Token、API Key 和 URL Token 参数会在进程输出进入 GUI 前被脱敏。

默认轮转配置：

```text
LOG_MAX_BYTES=5000000
LOG_BACKUP_COUNT=3
```

## 12. 配置和日志位置

### Windows

```text
%APPDATA%\LocalRepoMCP\config.json
%APPDATA%\LocalRepoMCP\secrets.json
%APPDATA%\LocalRepoMCP\mcp.jsonl
%APPDATA%\LocalRepoMCP\audit.jsonl
```

### Linux/macOS

```text
$XDG_CONFIG_HOME/local-repo-mcp/
```

未设置 `XDG_CONFIG_HOME` 时：

```text
~/.config/local-repo-mcp/
```

普通配置和 HTTP 密钥分开保存。控制面 Runtime API Key 不会被 GUI 持久化。

## 13. 运行回归测试

在源码仓库中执行：

```bash
python -m pytest -q -p no:cacheprovider
```

测试数量会随功能演进变化；工程验收以本次完整 pytest 输出的退出码和通过/跳过/失败统计为准，不在文档中固化易过期的测试数量。

## 14. 常见故障排查

### 仓库校验失败

确认路径存在并且属于 Git 工作区：

```bash
git -C /path/to/repository rev-parse --is-inside-work-tree
```

### 找不到 Git

安装 Git，并确认在启动 GUI 的同一环境中执行 `git --version` 能成功。

### STDIO 没有显示常驻进程

这是正常行为。STDIO 按客户端会话启动。使用**连接**进行验证，或让 MCP 客户端按生成的配置启动 Server。

### HTTP 启动失败

在 MCP 日志中检查：

- 端口已被占用；
- 仓库无效；
- Bearer Token 缺失；
- Host 或 Origin 配置错误；
- TLS 证书或私钥不存在；
- 非本机监听未配置 TLS 或可信代理；
- `HTTP_PUBLIC_URL` 与 MCP 路径不一致。

### HTTP 返回 401

确认客户端在 `Authorization` 请求头中发送了与配置完全一致的 Bearer Token。

### 找不到 Tunnel Client

填写 `tunnel-client` 的完整路径，或将其目录加入 `PATH`，然后重新执行**检测**。

### Tunnel 诊断失败

检查 Tunnel ID、Profile、Runtime API Key、生成的 MCP 命令和网络连接。不要把真实密钥复制到公开 Issue 中，应优先查看 Tunnel 日志。

### 没有 ripgrep 时检索较慢

找不到 `rg` 时，Local Repo MCP 会降级使用有边界的 Python 检索。安装 ripgrep 可以改善大型仓库检索性能，但不是必须依赖。

### 测试执行被拒绝

确认当前模式为 `test`，并且 `command_key` / `command_keys` 全部属于固定白名单；批量调用中任一 key 非法时整批会在执行前被拒绝。

## 15. 安全检查清单

使用写入、测试、Tunnel 或远程 HTTP 前：

- 核对目标仓库路径；
- 优先从 `read` 模式开始；
- 只有确实需要时才启用 `write` 或 `test`；
- `test` 模式只用于可信仓库；
- 保护 HTTP Token 和 Runtime API Key；
- 不要将明文 HTTP 暴露到远程网络；
- 明确配置 Host、Origin、Public URL 和可信代理地址；
- 保护配置目录和日志目录；
- 手工提交前检查 Git 状态和 Diff。

完整边界见[安全模型](SECURITY.md)。

## 16. 普通目录与 Git 初始化

配置的目录就是开放给 MCP 客户端的本地项目目录。该目录最初可以只是一个已经存在的普通文件夹。通过“浏览”选择目录时会立即检查 Git 状态；手工输入路径时，点击“连接”或“启动”前会再次检查。

目录尚未处于 Git 工作区时，GUI 会先要求用户明确确认，然后才执行 `git init`。取消后目录保持不变。该操作只创建 `.git` 元数据，不会创建 Commit、配置远程仓库或发布项目文件。

如果所选目录已经位于父级 Git 工作区中，Local Repo MCP 会使用现有仓库，不会创建嵌套 `.git`。目标机器仍需安装 Git，并可通过 `PATH` 找到。

该目录/Git 初始化行为持续由回归测试覆盖，验收以当前完整测试输出为准。
