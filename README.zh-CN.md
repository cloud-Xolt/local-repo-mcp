# Local Repo MCP

<p align="right"><a href="./README.md">English</a> · <strong>简体中文</strong></p>

<p align="center"><strong>将一个本地 Git 仓库安全接入任意 MCP 客户端。</strong></p>

<p align="center">
在不开放任意 Shell 和整个文件系统的前提下，读取、搜索、检查 Git 变更、应用经过验证的文本 Patch，并可选运行可信仓库中的测试。
</p>

## 为什么做这个项目？

Local Repo MCP 只解决一个明确问题：

> 让 ChatGPT、Claude、Cursor 和其他 MCP 客户端获得操作一个本地 Git 仓库所需的最小能力，同时让权限边界保持简单、透明、可理解。

它刻意不做企业 Agent 平台、策略引擎、RBAC、多租户网关或终端 Agent。

## 核心能力

- 只访问一个配置的 Git 仓库
- 默认只读
- 不提供任意 Shell
- 不提供无限制 `write_file`
- 仅通过经过验证的文本 Patch 写入
- Git 状态和 Diff 会过滤敏感路径
- 不执行 Git push、pull、checkout、reset、rebase、merge、stash 或 clean
- 可选运行可信仓库中的预定义测试
- 同时支持 STDIO 和 Streamable HTTP
- 可选 OpenAI Secure MCP Tunnel
- 简体中文和英文 GUI

## 架构

### 本地客户端使用 STDIO

```text
本地 MCP 客户端
      │
      │ 启动子进程
      ▼
Local Repo MCP（STDIO）
      │
      ▼
一个本地 Git 仓库
```

### URL 型客户端使用 Streamable HTTP

```text
MCP 客户端
    │
    │ http://127.0.0.1:8000/mcp
    ▼
Local Repo MCP（Streamable HTTP）
    │
    ▼
一个本地 Git 仓库
```

### ChatGPT + Secure MCP Tunnel

```text
ChatGPT
   │
OpenAI Secure MCP Tunnel
   │
tunnel-client
   │
Local Repo MCP（STDIO 或 HTTP）
   │
本地 Git 仓库
```

## MCP Tools

| Tool | 最低模式 | 说明 |
|---|---|---|
| `repo_list_files` | `read` | 列出允许访问的文件 |
| `repo_read_file` | `read` | 读取一个 UTF-8 文本文件 |
| `repo_search_code` | `read` | 固定字符串源码搜索 |
| `repo_git_status` | `read` | 返回过滤后的 Git 状态 |
| `repo_git_diff` | `read` | 返回过滤后的暂存或未暂存 Diff |
| `repo_apply_patch` | `write` | 应用一个经过验证的统一文本 Patch |
| `repo_run_test` | `test` | 运行一个预定义测试命令 |

## 权限模式

| 模式 | 能力 |
|---|---|
| `read` | 读取、搜索、Git 状态和 Diff |
| `write` | 只读能力 + 受控 Patch |
| `test` | 写入能力 + 预定义测试 |

建议始终从 `read` 开始。

## 传输方式

### STDIO

适合 MCP 客户端与仓库位于同一台机器，并且客户端能够启动本地子进程的场景。STDIO 没有 Host、Port 或 Endpoint URL。

### Streamable HTTP

适合只接受 URL 的 MCP 客户端、独立进程、局域网或跨设备场景。

默认地址：

```text
http://127.0.0.1:8000/mcp
```

默认安全策略：

- 仅监听 `127.0.0.1`；
- 启用 Host/Origin 校验；
- 可选 Bearer Token；
- 非本机监听必须开启 Bearer 认证并配置允许的 Host。

不要在不了解网络暴露风险的情况下绑定 `0.0.0.0`。非本机部署建议通过可信反向代理提供 HTTPS。

## 环境要求

- Python 3.11+
- Git 2.39+
- ripgrep（`rg`）
- 可选：OpenAI `tunnel-client`

不需要 Docker。

## 安装

```bash
git clone https://github.com/cloud-Xolt/local-repo-mcp.git
cd local-repo-mcp
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run_gui.py
```

Linux / macOS：

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run_gui.py
```

## GUI

GUI 只保留五个清晰页面：

1. **首页**：仓库、访问权限、传输方式和常用配置
2. **MCP 服务**：进程状态、真实 MCP 握手测试和客户端配置
3. **ChatGPT 连接**：Secure MCP Tunnel 配置与诊断
4. **日志**：MCP、Tunnel 和审计日志
5. **关于**：项目边界、版本、文档与仓库入口

常用配置直接展示；大小限制、Dirty Worktree、审计日志和 HTTP Allowlist 收纳在“高级配置”中。

GUI 会把普通配置保存到当前用户的配置目录。OpenAI Runtime API Key 只存在于当前进程内存中，绝不写入磁盘。HTTP Bearer Token 启用后单独保存，并使用受限文件权限。

## 不使用 GUI 启动

### STDIO

Linux / macOS：

```bash
export REPO_ROOT="/absolute/path/to/repository"
export MCP_MODE="read"
export MCP_TRANSPORT="stdio"
python server.py
```

Windows PowerShell：

```powershell
$env:REPO_ROOT = "C:\absolute\path\to\repository"
$env:MCP_MODE = "read"
$env:MCP_TRANSPORT = "stdio"
python server.py
```

本地客户端配置示例：

```json
{
  "mcpServers": {
    "local-repo": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/local-repo-mcp/server.py"],
      "env": {
        "REPO_ROOT": "/absolute/path/to/repository",
        "MCP_MODE": "read",
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

### Streamable HTTP

```bash
export REPO_ROOT="/absolute/path/to/repository"
export MCP_MODE="read"
export MCP_TRANSPORT="streamable-http"
export HTTP_HOST="127.0.0.1"
export HTTP_PORT="8000"
export HTTP_PATH="/mcp"
python server.py
```

连接地址：

```text
http://127.0.0.1:8000/mcp
```

开启 Bearer 认证：

```bash
export HTTP_AUTH_MODE="bearer"
export HTTP_AUTH_TOKEN="replace-with-a-random-token"
```

## 真实连接测试

GUI 的连接测试不是简单检查目录是否存在，而是：

1. 创建 MCP Client Session；
2. 完成协议初始化；
3. 获取 Tool 列表；
4. 验证预期只读 Tool；
5. 调用 `repo_git_status`；
6. 正常关闭连接。

STDIO 模式会启动临时子进程；HTTP 模式会连接正在运行的 Endpoint。

## ChatGPT 与 Secure MCP Tunnel

请从 OpenAI 官方渠道安装 `tunnel-client`。本项目不会自动下载或升级它。

STDIO Profile 示例：

```bash
export CONTROL_PLANE_API_KEY="sk-..."

tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile local-repo \
  --tunnel-id tunnel_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
  --mcp-command "/absolute/path/to/.venv/bin/python /absolute/path/to/local-repo-mcp/launch_mcp.py"

tunnel-client doctor --profile local-repo --explain
tunnel-client run --profile local-repo
```

GUI 支持检测可执行文件、初始化 Profile、运行 Doctor、启动和停止 Tunnel。Runtime API Key 只保存在内存中。

HTTP Tunnel 模式需要先启动 HTTP MCP Server。GUI 自动配置目前只支持本机无认证 HTTP Endpoint；自定义 Bearer HTTP Tunnel 请手动配置，或改用 STDIO Tunnel。

## 配置

### 核心配置

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `REPO_ROOT` | `.` | 唯一仓库根目录 |
| `MCP_MODE` | `read` | `read`、`write` 或 `test` |
| `MCP_TRANSPORT` | `stdio` | `stdio` 或 `streamable-http` |
| `MAX_FILE_BYTES` | `200000` | 最大可读文件 |
| `MAX_PATCH_BYTES` | `200000` | 最大 Patch |
| `MAX_SEARCH_RESULTS` | `50` | 搜索结果上限 |
| `MAX_OUTPUT_BYTES` | `20000` | Diff/测试输出上限 |
| `ALLOW_DIRTY_WORKTREE` | `false` | 是否允许修改已有未提交变更的工作区 |
| `AUDIT_LOG` | 空 | 可选 JSONL 审计日志 |
| `TEST_TIMEOUT_MAX` | `300` | 最大测试超时 |

### HTTP 配置

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `HTTP_HOST` | `127.0.0.1` | 监听地址 |
| `HTTP_PORT` | `8000` | 监听端口 |
| `HTTP_PATH` | `/mcp` | MCP Endpoint |
| `HTTP_AUTH_MODE` | `none` | `none` 或 `bearer` |
| `HTTP_AUTH_TOKEN` | 空 | Bearer Token |
| `HTTP_ALLOWED_HOSTS` | 本机值 | Host Allowlist |
| `HTTP_ALLOWED_ORIGINS` | 本机值 | Origin Allowlist |
| `HTTP_JSON_RESPONSE` | `true` | JSON 响应模式 |
| `HTTP_STATELESS` | `true` | 无状态 HTTP |
| `HTTP_MAX_REQUEST_BYTES` | `262144` | 最大请求体 |

## 安全模型

项目面向一个本地用户和一个配置仓库。

主要控制：

- 只接受相对路径；
- 拒绝父目录穿越；
- 拒绝符号链接；
- 阻断常见敏感文件；
- 拒绝二进制和非 UTF-8 文件读取；
- 使用固定字符串 `ripgrep`，并保持 `shell=False`；
- Git 状态和 Diff 过滤敏感路径；
- 仅允许文本 Patch 写入；
- 拒绝 Binary、Rename、Copy、Submodule、Symlink 和 Mode Change Patch；
- 检测 Patch 新增行中的部分常见凭证模式；
- 所有输入输出都有大小上限；
- 不提供任意 Shell；
- 不自动管理分支、Commit 或 Push。

能力边界：

- 常见凭证检测不是完整 Secret Scanner；
- 写模式会修改当前工作区；
- 测试模式会执行仓库代码，只能用于可信仓库；
- 用户确认由 MCP Client 负责；
- 用户应人工检查 `git diff`，并手动 Commit 和 Push。

详见 [SECURITY.md](./SECURITY.md)。

## 预定义测试

| Key | 命令 |
|---|---|
| `python_pytest` | `python -m pytest -q` |
| `go_test` | `go test ./...` |
| `node_test` | `npm test --` |
| `node_lint` | `npm run lint --` |
| `maven_test` | `mvn test` |
| `gradle_test` | `./gradlew test` |

用户不能传入任意命令或附加参数。

## 开发检查

```bash
python -m pytest tests/ -v
python -m compileall server.py launch_mcp.py run_gui.py src gui
```

## 项目范围

范围内：

- 一个本地 Git 仓库；
- 安全读取和搜索；
- 过滤后的 Git 检查；
- 经过验证的文本 Patch；
- 可选预定义测试；
- STDIO 和 Streamable HTTP；
- 可选 GUI 和 Secure MCP Tunnel。

范围外：

- 任意 Shell；
- 整个文件系统访问；
- RBAC 和多用户托管；
- 企业策略引擎或风险评分；
- 自动分支管理；
- 自动 Commit、Merge 或 Push；
- 云端执行与不可信代码沙箱；
- 自动安装 `tunnel-client`。

## License

MIT License，详见 [LICENSE](./LICENSE)。
