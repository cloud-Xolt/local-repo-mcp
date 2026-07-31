# Local Repo MCP

<p align="right">
  <a href="./README.md">English</a> · <strong>简体中文</strong>
</p>

<p align="center">
  <strong>将一个本地 Git 仓库安全接入 ChatGPT 和其他 MCP 客户端。</strong>
</p>

<p align="center">
  在不开放任意 Shell 和整个本地文件系统的前提下，读取、搜索、检查 Git 变更、应用受控 Patch，并可选运行可信仓库中的测试。
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="MCP Server" src="https://img.shields.io/badge/MCP-Server-6C47FF">
  <img alt="默认模式" src="https://img.shields.io/badge/default-read--only-2EA44F">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-blue">
</p>

---

## Local Repo MCP 是什么？

Local Repo MCP 是一个面向单个本地 Git 仓库的轻量、安全型 MCP Server。

它为 ChatGPT 和其他 MCP 客户端提供理解、检查和修改一个仓库所需的最小能力，同时刻意避免暴露广泛的操作系统权限。

支持：

- 列出仓库文件；
- 读取 UTF-8 源码文件；
- 搜索源码；
- 查看经过敏感路径过滤的 Git 状态和 Diff；
- 应用经过验证的文本 Patch；
- 可选运行可信仓库中的预定义测试；
- 可选通过 OpenAI Secure MCP Tunnel 接入 ChatGPT。

不提供：

- 任意 Shell；
- 整个文件系统访问；
- 任意文件写入；
- `git push`、`pull`、`checkout`、`reset`、`rebase` 或 `merge`。

---

## 为什么需要它？

AI 编码工具需要读取本地源码，但通用文件系统或终端权限可能远超实际需要。

Local Repo MCP 采用更小、更明确的权限模型：

```text
一个本地 Git 仓库
        +
默认只读
        +
不提供任意 Shell
        +
只通过 Patch 修改代码
        +
不自动发布 Git 变更
```

本项目刻意保持轻量。它不是企业 Agent 平台、策略引擎、多租户网关或云端编码服务。

---

## 核心特性

### 仅访问一个仓库

所有文件和 Git 操作都限制在配置的仓库根目录中。

服务器拒绝：

- 绝对路径；
- `../` 等父目录穿越；
- 符号链接；
- 配置仓库之外的路径；
- `.env`、私钥、凭证和 `.git` 内部文件等常见敏感内容。

### 默认只读

默认 `read` 模式只开放仓库检查能力。写入和测试能力必须由用户显式开启。

### 仅通过 Patch 写入

服务器不提供任意 `write_file`。

```text
检查 Patch 大小
        ↓
解析受影响路径
        ↓
阻断敏感目标
        ↓
检测常见凭证模式
        ↓
执行 git apply --check
        ↓
应用 Patch
        ↓
返回过滤后的 Git Diff
```

### 不提供任意 Shell

服务器不提供 `run_shell`、`run_command` 或同类 Tool。可选测试功能只接受预定义命令键。

### 可选双语 GUI

GUI 支持简体中文和英文，提供：

- 仓库选择；
- 权限模式选择；
- MCP 启动与停止；
- 可选 Secure MCP Tunnel 配置；
- 连接诊断；
- 实时日志；
- 可折叠高级配置。

### 可选接入 ChatGPT

本地 MCP 客户端可以通过 stdio 直接启动服务器。ChatGPT 可以通过 OpenAI Secure MCP Tunnel 访问本地 MCP Server，无需将服务公开暴露到互联网。

---

## 架构

### 本地 MCP 客户端

```text
Cursor / Claude Desktop / 其他 MCP 客户端
                     │
                     │ stdio
                     ▼
              Local Repo MCP
                     │
                     ▼
              本地 Git 仓库
```

### ChatGPT + Secure MCP Tunnel

```text
ChatGPT
   │
自定义 MCP App
   │
OpenAI Secure MCP Tunnel
   │
tunnel-client
   │
Local Repo MCP
   │
本地 Git 仓库
```

Secure MCP Tunnel 是可选组件。

---

## 权限模式

| 模式 | 界面名称 | 能力 |
|---|---|---|
| `read` | 只读 | 文件列表、读取、搜索、Git 状态和 Git Diff |
| `write` | 读写 | 只读能力 + 经过验证的 Patch 应用 |
| `test` | 读写与测试 | 写入能力 + 预定义测试命令 |

建议从 `read` 开始，仅在实际需要时开启更高权限。

---

## MCP Tools

| Tool | 最低模式 | 说明 |
|---|---|---|
| `repo_list_files` | `read` | 列出允许访问的仓库文件 |
| `repo_read_file` | `read` | 读取一个允许访问的 UTF-8 文本文件 |
| `repo_search_code` | `read` | 在结果数量受限的条件下搜索源码 |
| `repo_git_status` | `read` | 返回经过敏感路径过滤的 Git 状态 |
| `repo_git_diff` | `read` | 返回经过过滤的暂存或未暂存 Diff |
| `repo_apply_patch` | `write` | 验证并应用统一文本 Patch |
| `repo_run_test` | `test` | 运行一个预定义测试命令 |

项目刻意不提供任意 Shell、任意文件写入或危险 Git 操作。

---

## 环境要求

| 依赖 | 用途 |
|---|---|
| Python 3.11+ | MCP Server 和 GUI |
| Git 2.39+ | 仓库检查和 Patch 应用 |
| ripgrep（`rg`） | 快速源码搜索 |
| OpenAI `tunnel-client` | 可选 ChatGPT 连接 |

不需要 Docker。

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/cloud-Xolt/local-repo-mcp.git
cd local-repo-mcp
```

### 2. 创建虚拟环境

#### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

#### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## 使用 GUI

推荐通过 GUI 完成配置和启动。

### Windows

```powershell
python run_gui.py
```

### Linux / macOS

```bash
python run_gui.py
```

### 首次使用流程

1. 选择一个本地 Git 仓库；
2. 选择访问权限；
3. 保存配置；
4. 启动 MCP Server；
5. 连接 MCP 客户端。

需要接入 ChatGPT 时，应先确认本地 MCP 正常工作，再配置可选 Tunnel。

---

## GUI 页面

### 概览

显示 MCP 状态、Tunnel 状态、当前仓库、权限模式、快捷操作和最近消息。

### MCP 配置

包含仓库路径、权限模式、保存、启动、停止和本地连接测试。

### Tunnel

包含 `tunnel-client` 路径、Tunnel ID、Profile、临时 Runtime API Key、初始化、Doctor、启动和停止。

Runtime API Key 不得持久化到 `config.json`。

### 日志

显示 MCP 日志、Tunnel 日志、审计事件和诊断信息。

### 高级配置

默认收起：

- 最大文件大小；
- 最大 Patch 大小；
- 最大搜索结果数；
- 最大输出大小；
- Dirty Worktree 策略；
- 审计日志路径；
- 测试超时时间。

整个界面支持中英文切换，正式界面不应在每个字段中长期同时显示两种语言。

---

## 命令行启动

### Linux / macOS

```bash
export REPO_ROOT="/absolute/path/to/your/repository"
export MCP_MODE="read"
export AUDIT_LOG=""
python server.py
```

### Windows PowerShell

```powershell
$env:REPO_ROOT = "C:\absolute\path\to\your\repository"
$env:MCP_MODE = "read"
$env:AUDIT_LOG = ""
python server.py
```

服务器通过 stdio 通信。

---

## 配置本地 MCP 客户端

```json
{
  "mcpServers": {
    "local-repo": {
      "command": "/absolute/path/to/local-repo-mcp/.venv/bin/python",
      "args": [
        "/absolute/path/to/local-repo-mcp/server.py"
      ],
      "env": {
        "REPO_ROOT": "/absolute/path/to/your/repository",
        "MCP_MODE": "read",
        "MAX_FILE_BYTES": "200000",
        "MAX_PATCH_BYTES": "200000",
        "MAX_SEARCH_RESULTS": "50",
        "MAX_OUTPUT_BYTES": "20000",
        "ALLOW_DIRTY_WORKTREE": "false",
        "AUDIT_LOG": ""
      }
    }
  }
}
```

Windows 使用 `.venv\Scripts\python.exe`。

---

## 连接 ChatGPT

ChatGPT 接入是可选功能。

Local Repo MCP 保持运行在本地，OpenAI Secure MCP Tunnel 提供私有连接路径。

### 前置条件

需要：

1. ChatGPT Developer Mode 权限；
2. OpenAI Platform Tunnel ID；
3. `tunnel-client` Runtime API Key；
4. OpenAI 官方 `tunnel-client`；
5. 已正常运行的 Local Repo MCP。

### 初始化 stdio Profile

```bash
export CONTROL_PLANE_API_KEY="sk-..."

tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile local-repo \
  --tunnel-id tunnel_0123456789abcdef0123456789abcdef \
  --mcp-command "/absolute/path/to/local-repo-mcp/.venv/bin/python /absolute/path/to/local-repo-mcp/server.py"
```

检查并启动：

```bash
tunnel-client doctor --profile local-repo --explain
tunnel-client run --profile local-repo
```

Local Repo MCP 不自动下载或更新 `tunnel-client`。

---

## 配置说明

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `REPO_ROOT` | `.` | 单个 Git 仓库路径 |
| `MCP_MODE` | `read` | `read`、`write` 或 `test` |
| `MAX_FILE_BYTES` | `200000` | 单个可读取文件最大大小 |
| `MAX_PATCH_BYTES` | `200000` | 单个 Patch 最大大小 |
| `MAX_SEARCH_RESULTS` | `50` | 最大搜索结果数 |
| `MAX_OUTPUT_BYTES` | `20000` | 最大 Diff 或进程输出大小 |
| `ALLOW_DIRTY_WORKTREE` | `false` | 是否允许在已有变更时应用 Patch |
| `AUDIT_LOG` | 空 | 可选审计日志路径 |
| `TEST_TIMEOUT_MAX` | `300` | 最大测试超时时间，单位秒 |

建议首次使用：

```dotenv
REPO_ROOT=/absolute/path/to/repository
MCP_MODE=read
MAX_FILE_BYTES=200000
MAX_PATCH_BYTES=200000
MAX_SEARCH_RESULTS=50
MAX_OUTPUT_BYTES=20000
ALLOW_DIRTY_WORKTREE=false
AUDIT_LOG=
TEST_TIMEOUT_MAX=300
```

---

## 测试命令

仅 `test` 模式允许执行测试。

| `command_key` | 命令 |
|---|---|
| `python_pytest` | `python -m pytest -q` |
| `go_test` | `go test ./...` |
| `node_test` | `npm test --` |
| `node_lint` | `npm run lint --` |
| `maven_test` | `mvn test` |
| `gradle_test` | `./gradlew test` |

用户不能提交任意命令或附加参数。

> **警告：** 测试模式会执行配置仓库中的代码，只能对可信仓库启用。

---

## 安全模型

Local Repo MCP 面向一个本地用户、一个配置的 Git 仓库和一个 MCP Server 进程。

服务器：

- 将文件访问限制在 `REPO_ROOT`；
- 拒绝绝对路径、父目录穿越和符号链接；
- 阻断常见敏感文件；
- 拒绝二进制和不支持的文本文件；
- 限制文件、Patch、搜索、Diff 和进程输出大小；
- 从 Git 状态和 Diff 中过滤被阻断路径；
- 使用固定参数并保持 `shell=False`；
- 仅通过经过验证的文本 Patch 修改代码；
- 阻断新增内容中的部分常见凭证模式；
- 不执行 Git push、pull、checkout、reset、rebase、merge、stash 或 clean；
- 不提供任意 Shell；
- 不持久化 Tunnel Runtime API Key。

常见阻断路径：

```text
.env
.env.*
.git/**
.ssh/**
*.pem
*.key
*.p12
*.pfx
id_rsa
id_ed25519
credentials/**
secrets/**
.github/workflows/**    # Patch 写入时阻断
```

支持的 Patch：

```text
普通文本文件新增
普通文本文件修改
普通文本文件删除
```

拒绝的 Patch：

```text
二进制 Patch
创建符号链接
重命名
复制
Submodule 变更
文件模式变更
```

### 能力边界

- 常见凭证检测不是完整 Secret Scanner；
- 用户确认由 MCP Client 负责；
- 写模式会修改当前工作区；
- 测试模式会执行仓库代码；
- 提交前应检查 `git diff`；
- Commit 和 Push 应由用户手动完成；
- 测试模式只能用于可信仓库。

---

## 审计日志

审计日志是可选功能，可记录时间、Tool 名称、结果、目标路径、输入大小和短 Hash。

不得记录完整文件内容、完整 Patch、搜索 Query、API Key、Token、密码或完整测试输出。

将 `AUDIT_LOG` 留空即可关闭。

---

## 项目范围

### 范围内

- 一个配置的本地 Git 仓库；
- 文件列表和读取；
- 结果受限的源码搜索；
- 过滤后的 Git 状态和 Diff；
- 经过验证的文本 Patch；
- 可选预定义测试命令；
- 可选 GUI；
- 可选 Secure MCP Tunnel。

### 范围外

- 任意 Shell；
- 通用文件系统访问；
- 多用户认证；
- RBAC；
- 企业策略引擎；
- 风险评分；
- Session 编排；
- 自动分支管理；
- 自动 Commit 或 Push；
- 云端仓库托管；
- 不可信代码沙箱；
- 自动安装 `tunnel-client`。

明显扩大这些边界的 Pull Request 可能会被拒绝。

---

## 常见问题

### 找不到 `ripgrep`

```bash
rg --version
```

### 选择的目录不是 Git 仓库

```bash
git -C /path/to/repository status
```

### Worktree 不干净导致 Patch 被拒绝

```bash
git status
git diff
```

手动 Commit 或 Stash，也可以谨慎开启 `ALLOW_DIRTY_WORKTREE=true`。

### ChatGPT 看不到 Tunnel

检查 Tunnel ID、`tunnel-client` 运行状态、Doctor 结果、Workspace 关联和账号权限。

---

## 开发

```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -v
python -m compileall server.py src gui
```

重点安全测试应覆盖路径穿越、绝对路径、符号链接逃逸、敏感文件阻断、ripgrep 参数注入、Git Diff 过滤、不支持的 Patch、凭证模式阻断、API Key 持久化、命令白名单和 `shell=False`。

---

## Roadmap

计划：

- 简化安装和打包；
- PyPI 发布；
- Windows 便携版本；
- MCP Registry 元数据；
- 更完整的 MCP 客户端配置说明；
- 更多安全测试；
- 更好的 GUI 可访问性和国际化；
- 更清晰的诊断信息。

不计划：

```text
RBAC
企业策略管理
多用户托管
任意 Shell
自动 Git Push
云端执行平台
```

---

## 贡献

欢迎贡献。请保持在文档定义的项目范围内，不扩大操作系统或 Git 权限，补充测试，并在面向用户的行为变化时同步更新中英文文档。

适合贡献的方向包括跨平台兼容、GUI 易用性、国际化、安全测试、打包、文档、错误提示和 MCP 客户端示例。

---

## License

Local Repo MCP 使用 MIT License。

---

## 参考资料

- OpenAI Secure MCP Tunnel  
  https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
- OpenAI `tunnel-client`  
  https://github.com/openai/tunnel-client
- ChatGPT Developer Mode and MCP Apps  
  https://help.openai.com/en/articles/12584461-developer-mode-apps-and-full-mcp-connectors-in-chatgpt-beta
- Model Context Protocol  
  https://modelcontextprotocol.io
- MCP Python SDK  
  https://github.com/modelcontextprotocol/python-sdk
