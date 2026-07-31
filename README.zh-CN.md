# Local Repo MCP

<p align="right">
  <a href="./README.md">English</a> · <strong>简体中文</strong>
</p>

> 通过 [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) 以**最小权限**方式将本地 Git 仓库接入 ChatGPT，无需暴露公网 MCP 入口。

```text
ChatGPT → Custom MCP App → Secure MCP Tunnel → tunnel-client → Local Repo MCP → 本地仓库
```

## 特性

- **Policy Engine** — 基于 `security/rules.yaml` 的读写/执行策略
- **Session 模型** — 写入与测试需先创建 Session
- **Git 分支沙箱** — 受保护分支自动切到 `agent/{session_id}`
- **路径沙箱** — 所有操作限制在 `REPO_ROOT` 内
- **Secret 扫描** — Patch 应用前检测密钥与凭证
- **Docker 测试沙箱** — 隔离容器运行（禁网络、只读挂载）
- **Prompt Injection 防护** — 文件内容标记为 `UNTRUSTED_DATA`
- **审计日志** — 结构化记录，敏感信息自动脱敏
- **GUI 控制面板** — 全部配置可视化，一键启动与监控

## 项目结构

```text
local-repo-mcp/
├── server.py
├── security/          # Policy Engine、Secret Scanner、rules.yaml
├── session/           # Session Manager
├── audit/             # 审计框架
├── repo/              # 文件系统与 Git 控制
├── sandbox/           # Docker 测试沙箱
├── gui/               # GUI 控制面板
├── run_gui.py
├── start_gui.bat
├── requirements.txt
├── .env.example
└── systemd/
```

## 环境要求

| 依赖 | 用途 |
|------|------|
| Python 3.11+ | MCP Server 运行时 |
| Git 2.39+ | 仓库操作 |
| ripgrep（`rg`） | 代码搜索 |
| Docker | 测试沙箱执行 |
| [tunnel-client](https://github.com/openai/tunnel-client) | ChatGPT 接入 |

## 快速开始

### 1. 安装依赖

```bash
git clone git@github.com:cloud-Xolt/local-repo-mcp.git
cd local-repo-mcp
python -m venv .venv

# Windows
.venv\Scripts\activate
.venv\Scripts\pip install -r requirements.txt

# Linux / macOS
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 使用 GUI（推荐）

**Windows：** 双击 `start_gui.bat`

```bash
python run_gui.py
```

GUI 支持配置：仓库路径、运行模式、策略文件、Session 文件、受保护分支、写入 deny 规则、测试白名单、Docker 沙箱参数、Tunnel 连接等。

点击 **保存配置 · 同步策略** 会写入 `config.json`、`.env` 和 `rules.yaml`。

### 3. 命令行启动

```bash
export REPO_ROOT=/path/to/your/repo
export MCP_MODE=read
export POLICY_RULES=./security/rules.yaml
export AUDIT_LOG=./audit.log

python server.py
```

## 接入 ChatGPT

### 前置条件

1. ChatGPT 工作区已开启 Developer Mode
2. OpenAI Platform 已创建 Tunnel 并关联到目标工作区
3. 已安装 `tunnel-client`

### 初始化 Tunnel

```bash
export CONTROL_PLANE_API_KEY="sk-..."

tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile local-repo \
  --tunnel-id tunnel_xxxxxxxx \
  --mcp-command "bash -lc 'cd /opt/local-repo-mcp && source .venv/bin/activate && REPO_ROOT=/opt/repos/project-a MCP_MODE=read python server.py'"

tunnel-client doctor --profile local-repo --explain
tunnel-client run --profile local-repo
```

### 创建 Custom MCP App

在 ChatGPT 中：**Apps → Create developer-mode app → Connection 选择 Tunnel → Scan Tools → Create**

## 推荐工作流

```text
repo_session_start(user, permission="write")
  → repo_prepare_patch(patch, session_id)
  → repo_apply_patch(patch, session_id)
  → repo_run_test(command_key, session_id)
  → repo_session_end(session_id)
```

## MCP 工具

| 工具 | 模式 | 说明 |
|------|------|------|
| `repo_session_start` | write | 创建 Session 与 agent 分支 |
| `repo_session_end` | write | 结束 Session |
| `repo_list_files` | read | 列出仓库文件 |
| `repo_read_file` | read | 读取文件（UNTRUSTED 包装） |
| `repo_search_code` | read | ripgrep 搜索 |
| `repo_git_status` | read | git status |
| `repo_git_diff` | read | git diff |
| `repo_prepare_patch` | write | 校验 patch（不应用） |
| `repo_apply_patch` | write | 应用 patch |
| `repo_run_test` | test | Docker 沙箱运行测试 |

## 配置说明

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `REPO_ROOT` | `.` | 仓库根目录 |
| `MCP_MODE` | `read` | `read` / `write` / `test` / `ship` |
| `MAX_FILE_BYTES` | `200000` | 单文件最大读取字节 |
| `MAX_PATCH_BYTES` | `200000` | Patch 最大字节 |
| `ALLOW_DIRTY_WORKTREE` | `false` | 是否允许 dirty 时 apply patch |
| `AUDIT_LOG` | `./audit.log` | 审计日志路径 |
| `POLICY_RULES` | `./security/rules.yaml` | 策略文件路径 |
| `SESSIONS_FILE` | `./sessions.json` | Session 存储路径 |
| `SANDBOX_MEMORY` | `2g` | Docker 沙箱内存 |
| `SANDBOX_CPUS` | `2` | Docker 沙箱 CPU |
| `SANDBOX_TMPFS_MB` | `512` | 沙箱 tmpfs 大小 (MB) |
| `TEST_TIMEOUT_MAX` | `300` | 测试超时上限（秒） |

完整模板见 [`.env.example`](./.env.example)。

## 推荐上线阶段

| 阶段 | 模式 | 能力 |
|------|------|------|
| 一 | `read` | 列表、读取、搜索、git status/diff |
| 二 | `write` | + patch 校验与应用 |
| 三 | `test` | + Docker 沙箱测试 |

**永不开放：** 任意 Shell、`git push`、`git reset`、`git rebase` 等。

## 安全提示

- 勿将 `config.json`、`.env`、API Key 提交到 Git
- 默认 `read` 模式，验证后再逐步开放
- `git push` 建议手动完成

## Linux 部署

参考 [`systemd/`](./systemd/) 目录下的 service 示例，以低权限用户（如 `repo-mcp`）运行。

## 参考资料

- [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [tunnel-client](https://github.com/openai/tunnel-client)
- [ChatGPT Developer Mode](https://help.openai.com/en/articles/12584461-developer-mode-apps-and-full-mcp-connectors-in-chatgpt-beta)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## License

MIT
