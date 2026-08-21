# Local Repo MCP 1.4.0

[简体中文](README.zh-CN.md) | [English](README.md)

面向单个本地 Git 仓库的轻量、安全型 MCP Server。

**第一约束：** 只提供受控的仓库读写、测试/构建/检查执行与可核验结果回传；保持轻量、单仓库、固定工具面，不演进为 Agent、任务编排平台或通用远程 Shell。

## 核心能力

- 固定 8 个 MCP 工具：文件列表、UTF-8 读取、固定字符串搜索、过滤后的 Git 状态与差异、原子统一 Patch、可选本地 commit、白名单验证命令。
- `read`、`write`、`test` 三种权限模式。
- 支持 STDIO、OpenAI Secure MCP Tunnel 和 Streamable HTTP。
- 远程 HTTP 支持原生 HTTPS/mTLS，也支持可信 TLS 反向代理。
- 提供 Bearer 认证、Host/Origin 限制、请求与输出上限、敏感路径过滤、审计日志和跨进程仓库写锁。
- GUI 自动保存配置：STDIO 使用“连接”，HTTP 使用“启动/停止”，不再重复显示“保存”和“验证连接”。
- 日志中心按 MCP、Tunnel、审计和安全事件分类展示，支持搜索、级别过滤、易读摘要、原始 JSON、实时刷新、凭证脱敏和文件轮转。

## 源码目录启动

Windows：

```powershell
start_gui.bat
```

Linux/macOS：

```bash
./start_gui.sh
```

无图形界面（SSH/服务器）时使用交互式命令行：

```bash
chmod +x start_cli.sh
./start_cli.sh
```

启动脚本会创建 `.venv`，并在 `requirements.txt` 变化时自动同步依赖。

## 安装后的命令入口

```bash
pip install .
local-repo-mcp-gui
local-repo-mcp-cli
local-repo-mcp
```

源码模式和安装模式统一使用 `mcp_app.launcher`，不依赖仓库根目录中的包装脚本。

## 远程 HTTP

远程 HTTP 不绑定 GCP 或任何特定云平台，可部署在自建服务器、虚拟机、容器、Kubernetes、反向代理和云负载均衡之后。

可选择：

1. 原生 TLS：配置 `HTTP_TLS_CERTFILE` 与 `HTTP_TLS_KEYFILE`；需要 mTLS 时再配置 `HTTP_TLS_CLIENT_CA`。
2. 可信 TLS 反向代理：配置 `HTTP_TLS_TERMINATED_PROXY=true`、`HTTP_PUBLIC_URL=https://host/mcp` 和明确的 `HTTP_PROXY_TRUSTED_IPS`。

支持 `0.0.0.0` 等通配监听，但必须配置 HTTPS `HTTP_PUBLIC_URL`，且 URL 路径必须与 `HTTP_PATH` 一致。

详细说明见 `docs/DEPLOYMENT.md` 和 `docs/SECURITY.md`。

## 测试

```bash
python -m pytest -q -p no:cacheprovider
```

Local Repo MCP 不会执行 checkout、reset、rebase、merge、pull、push 或 amend。本地 `git commit` 默认关闭，需在 GUI / `ALLOW_GIT_COMMIT` 显式开启，且仅限 write/test 模式。

## 文档入口

- [完整使用教程](docs/USAGE.zh-CN.md) — 安装、首次启动、STDIO、Secure MCP Tunnel、Streamable HTTP、日志、测试和故障排查。
- [部署指南](docs/DEPLOYMENT.md) — 原生 HTTPS、mTLS、反向代理、systemd、容器和 Kubernetes。
- [安全模型](docs/SECURITY.md) — 仓库边界、HTTP 控制、密钥、日志和可信测试执行。
- [安全策略](SECURITY.md) — 产品安全边界与漏洞报告说明。

## 环境要求

- Python 3.11 或更高版本。
- `PATH` 中可以找到 Git。
- 一个需要开放给 MCP 客户端的本地 Git 工作区。
- 只有使用 OpenAI Secure MCP Tunnel 时才需要 `tunnel-client`。

## 权限模式

| 模式 | 读取/列表/检索/状态/Diff | 应用受校验 Patch | 可选本地 commit | 运行白名单验证命令 |
| --- | --- | --- | --- | --- |
| `read` | 支持 | 不支持 | 不支持 | 不支持 |
| `write` | 支持 | 支持 | 开启后支持 | 不支持 |
| `test` | 支持 | 支持 | 开启后支持 | 支持 |

Test 模式会以当前操作系统用户权限执行仓库代码。该模式不是沙箱，只能用于可信仓库。

## MCP 工具

| 工具 | 作用 |
| --- | --- |
| `repo_list_files` | 列出指定仓库范围内允许访问的文件。 |
| `repo_read_file` | 读取允许访问的 UTF-8 文本文件；PNG/JPEG 以 MCP 图片内容返回。 |
| `repo_search_code` | 执行有数量和输出限制的固定字符串检索。 |
| `repo_git_status` | 返回经过敏感路径过滤的 Git 工作区状态。 |
| `repo_git_diff` | 返回经过过滤和大小限制的 Git Diff。 |
| `repo_apply_patch` | 原子应用一个经过校验的统一文本 Patch；单次可修改多个文件，任一目标失败则整体不应用。 |
| `repo_git_commit` | 在启用 `ALLOW_GIT_COMMIT` 时，为允许的待提交改动创建一次本地 Git commit；可选 `paths` 限定暂存范围。 |
| `repo_run_test` | 在 `test` 模式运行一个或一批白名单 test/build/lint/check 命令；返回可核验的退出码与 stdout/stderr。 |

`repo_run_test` 保留历史工具名以兼容现有客户端，内部统一由受控命令执行层处理。当前白名单包括 `python_pytest`、`go_test`、`go_build`、`go_vet`、`node_test`、`node_build`、`node_lint`、`maven_test`、`maven_build`、`gradle_test`、`gradle_build`。

单命令继续传 `command_key`。批量执行传 `command_keys`（最多 8 个），整批命令会在执行前完成白名单校验，然后按顺序执行；`stop_on_failure=true` 时遇到首个失败即停止，设为 `false` 时继续执行剩余命令。这里的“批量”只是一次 MCP 调用中的有界顺序执行，不引入队列、后台任务或调度器。

每个已启动命令都返回统一证据：

- `command_key` / `command_kind` / `command`
- `status` / `success` / `exit_code`（兼容保留 `returncode`）
- `stdout` / `stderr` 及截断标志
- `duration_ms` / `timeout_seconds`

超时或输出达到保护上限时同样返回结构化失败和已经捕获的输出，不会因为异常路径丢掉核验证据。命令生命周期写入运行/审计日志，但 stdout/stderr 不写入日志。

全部 8 个公开工具都发布明确的 MCP 输入/输出协议契约。服务端依赖 MCP SDK 原生 structured output 生成能力，不针对 GPT 或其他客户端手工改 schema；GUI 的连接验证会在接受连接前检查工具 schema 是否缺失或无效。可选集合参数使用“可选参数 + 非空数组 schema”表达，而不是 nullable union。

`src/tools/contracts.py` 是公开工具面的统一协议契约模块。协议回归直接检查真实 `MCPServer.list_tools()` 返回值，包括固定 8 个 Tool、每个 Tool 必须存在 `outputSchema`，以及输入 schema 的兼容性要求。

## 首次使用流程

1. 启动 GUI。
2. 选择目标 Git 工作区。
3. 选择 `read`、`write` 或 `test` 权限模式。
4. 选择 STDIO 或 Streamable HTTP。
5. 使用 STDIO 时点击**连接**，验证 MCP initialize、工具发现和仓库身份。
6. 使用 HTTP 时配置 Bearer Token，点击**启动**，然后点击**连接**。
7. 在 **MCP Server** 页面复制生成的客户端配置。

[完整使用教程](docs/USAGE.zh-CN.md)包含 STDIO、Tunnel、HTTP、日志、测试和故障排查的全部操作步骤。

## ChatGPT 与其他 MCP 客户端

Local Repo MCP 可以支持 ChatGPT 在所选权限模式下构建和维护本地 Git 项目，但并不只面向 ChatGPT。其他兼容 MCP 的编码 Agent、IDE、桌面客户端和自动化平台，也可以通过 STDIO 或 Streamable HTTP 接入，并获得相同的工具和安全控制。

新建本地项目时，在 GUI 中选择空目录，明确确认 Git 初始化后，再使用 `write` 或 `test` 模式。详细说明见[客户端兼容性与本地项目构建流程](docs/CLIENTS.zh-CN.md)。


当前 GUI 行为：选择普通目录后会立即检查 Git 状态，并弹出明确确认框。确认后才执行 `git init`；取消则目录保持不变。程序不会静默初始化，也不会创建 Commit 或远程仓库。若所选目录位于父级 Git 工作区内，不能把该子目录作为独立安全边界；GUI 会提示切换到实际的 Git 工作区根目录。
