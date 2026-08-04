# Local Repo MCP 1.3.0

[简体中文](README.zh-CN.md) | [English](README.md)

面向单个本地 Git 仓库的轻量、安全型 MCP Server。

## 核心能力

- 固定 7 个 MCP 工具：文件列表、UTF-8 读取、固定字符串搜索、过滤后的 Git 状态与差异、统一 Patch 写入、预定义测试。
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

启动脚本会创建 `.venv`，并在 `requirements.txt` 变化时自动同步依赖。

## 安装后的命令入口

```bash
pip install .
local-repo-mcp-gui
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

Local Repo MCP 不会执行 checkout、commit、reset、rebase、merge、pull 或 push。

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

| 模式 | 读取/列表/检索/状态/Diff | 应用受校验 Patch | 运行预定义测试 |
| --- | --- | --- | --- |
| `read` | 支持 | 不支持 | 不支持 |
| `write` | 支持 | 支持 | 不支持 |
| `test` | 支持 | 支持 | 支持 |

Test 模式会以当前操作系统用户权限执行仓库代码。该模式不是沙箱，只能用于可信仓库。

## MCP 工具

| 工具 | 作用 |
| --- | --- |
| `repo_list_files` | 列出指定仓库范围内允许访问的文件。 |
| `repo_read_file` | 读取一个允许访问的 UTF-8 文本文件。 |
| `repo_search_code` | 执行有数量和输出限制的固定字符串检索。 |
| `repo_git_status` | 返回经过敏感路径过滤的 Git 工作区状态。 |
| `repo_git_diff` | 返回经过过滤和大小限制的 Git Diff。 |
| `repo_apply_patch` | 应用一个经过校验的统一文本 Patch。 |
| `repo_run_test` | 在 `test` 模式运行一个预定义测试命令。 |

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

新建本地项目时，先在空目录中执行 `git init`，再在 GUI 中选择该目录并使用 `write` 或 `test` 模式。详细说明见[客户端兼容性与本地项目构建流程](docs/CLIENTS.zh-CN.md)。


当前 GUI 行为：选择普通目录后会立即检查 Git 状态，并弹出明确确认框。确认后才执行 `git init`；取消则目录保持不变。程序不会静默初始化，也不会创建 Commit 或远程仓库。若所选目录位于父级 Git 工作区内，不能把该子目录作为独立安全边界；GUI 会提示切换到实际的 Git 工作区根目录。
