# Local Repo MCP

[中文](#中文) · [English](#english)

---

## 中文

将本地 Git 代码仓库以**最小权限**方式接入 ChatGPT，配合 [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) 使用，无需把 MCP Server 暴露到公网。

```text
ChatGPT → Custom MCP App → Secure MCP Tunnel → tunnel-client → Local Repo MCP → 本地仓库
```

### 特性

- **Policy Engine**：基于 `security/rules.yaml` 的读写/执行策略
- **Session 模型**：写入与测试需先创建 Session
- **Git 分支沙箱**：受保护分支自动切到 `agent/{session_id}`
- **路径沙箱**：所有操作限制在 `REPO_ROOT` 内
- **Secret 扫描**：Patch 应用前检测密钥与凭证
- **Docker 测试沙箱**：测试命令在隔离容器中运行（禁网络、只读挂载）
- **Prompt Injection 防护**：文件内容标记为 UNTRUSTED_DATA
- **审计日志**：结构化记录，敏感信息自动脱敏
- **GUI 控制面板**：全部配置可视化，一键启动与监控

### 项目结构

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

### 环境要求

- Python 3.11+
- Git 2.39+
- ripgrep（`rg`）
- Docker（运行测试沙箱时需要）
- [tunnel-client](https://github.com/openai/tunnel-client)（接入 ChatGPT 时需要）

### 快速开始

#### 1. 安装依赖

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

#### 2. 使用 GUI（推荐）

**Windows：** 双击 `start_gui.bat`

```bash
python run_gui.py
```

GUI 支持配置：仓库路径、运行模式、策略文件、Session 文件、受保护分支、写入 deny 规则、测试白名单、Docker 沙箱参数、Tunnel 连接等。点击 **保存配置 · 同步策略** 会写入 `config.json`、`.env` 和 `rules.yaml`。

#### 3. 命令行启动

```bash
export REPO_ROOT=/path/to/your/repo
export MCP_MODE=read
export POLICY_RULES=./security/rules.yaml
export AUDIT_LOG=./audit.log

python server.py
```

### 推荐工作流

```text
repo_session_start(user, permission="write")
  → repo_prepare_patch(patch, session_id)
  → repo_apply_patch(patch, session_id)
  → repo_run_test(command_key, session_id)
  → repo_session_end(session_id)
```

### MCP 工具

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

### 配置说明

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

### 推荐上线阶段

1. **阶段一** — `MCP_MODE=read`：只读
2. **阶段二** — `MCP_MODE=write`：开放 patch
3. **阶段三** — `MCP_MODE=test`：开放 Docker 测试

**永不开放：** 任意 Shell、`git push`、`git reset`、`git rebase` 等。

### 安全提示

- 勿将 `config.json`、`.env`、API Key 提交到 Git
- 默认 `read` 模式，验证后再逐步开放
- `git push` 建议手动完成

### 参考资料

- [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [tunnel-client](https://github.com/openai/tunnel-client)
- [ChatGPT Developer Mode](https://help.openai.com/en/articles/12584461-developer-mode-apps-and-full-mcp-connectors-in-chatgpt-beta)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

---

## English

Connect a local Git repository to ChatGPT with **least privilege**, using the [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels). Your MCP Server never needs a public endpoint.

```text
ChatGPT → Custom MCP App → Secure MCP Tunnel → tunnel-client → Local Repo MCP → Local Repo
```

### Features

- **Policy Engine**: read/write/execute rules via `security/rules.yaml`
- **Session model**: write and test operations require an active session
- **Git branch sandbox**: protected branches auto-switch to `agent/{session_id}`
- **Path sandbox**: all operations confined to `REPO_ROOT`
- **Secret scanning**: blocks credentials in patches before apply
- **Docker test sandbox**: tests run in isolated containers (no network, read-only mount)
- **Prompt injection mitigation**: file content wrapped as UNTRUSTED_DATA
- **Audit logging**: structured logs with sensitive data redaction
- **GUI control panel**: full configuration, one-click start and monitoring

### Project Structure

```text
local-repo-mcp/
├── server.py
├── security/          # Policy Engine, Secret Scanner, rules.yaml
├── session/           # Session Manager
├── audit/             # Audit framework
├── repo/              # Filesystem & Git control
├── sandbox/           # Docker test sandbox
├── gui/               # GUI control panel
├── run_gui.py
├── start_gui.bat
├── requirements.txt
├── .env.example
└── systemd/
```

### Requirements

- Python 3.11+
- Git 2.39+
- ripgrep (`rg`)
- Docker (required for test sandbox)
- [tunnel-client](https://github.com/openai/tunnel-client) (for ChatGPT integration)

### Quick Start

#### 1. Install

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

#### 2. GUI (Recommended)

**Windows:** double-click `start_gui.bat`

```bash
python run_gui.py
```

The GUI exposes all settings: repo path, mode, policy file, sessions file, protected branches, write deny rules, test allowlist, Docker sandbox limits, and Tunnel credentials. **Save Config** writes `config.json`, `.env`, and `rules.yaml`.

#### 3. CLI

```bash
export REPO_ROOT=/path/to/your/repo
export MCP_MODE=read
export POLICY_RULES=./security/rules.yaml
export AUDIT_LOG=./audit.log

python server.py
```

### Recommended Workflow

```text
repo_session_start(user, permission="write")
  → repo_prepare_patch(patch, session_id)
  → repo_apply_patch(patch, session_id)
  → repo_run_test(command_key, session_id)
  → repo_session_end(session_id)
```

### MCP Tools

| Tool | Mode | Description |
|------|------|-------------|
| `repo_session_start` | write | Create session and agent branch |
| `repo_session_end` | write | End session |
| `repo_list_files` | read | List repository files |
| `repo_read_file` | read | Read file (UNTRUSTED wrapper) |
| `repo_search_code` | read | Search with ripgrep |
| `repo_git_status` | read | git status |
| `repo_git_diff` | read | git diff |
| `repo_prepare_patch` | write | Validate patch without applying |
| `repo_apply_patch` | write | Apply patch |
| `repo_run_test` | test | Run test in Docker sandbox |

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REPO_ROOT` | `.` | Repository root |
| `MCP_MODE` | `read` | `read` / `write` / `test` / `ship` |
| `MAX_FILE_BYTES` | `200000` | Max file read size (bytes) |
| `MAX_PATCH_BYTES` | `200000` | Max patch size (bytes) |
| `ALLOW_DIRTY_WORKTREE` | `false` | Allow patch on dirty worktree |
| `AUDIT_LOG` | `./audit.log` | Audit log path |
| `POLICY_RULES` | `./security/rules.yaml` | Policy rules file |
| `SESSIONS_FILE` | `./sessions.json` | Session storage path |
| `SANDBOX_MEMORY` | `2g` | Docker sandbox memory |
| `SANDBOX_CPUS` | `2` | Docker sandbox CPUs |
| `SANDBOX_TMPFS_MB` | `512` | Sandbox tmpfs size (MB) |
| `TEST_TIMEOUT_MAX` | `300` | Max test timeout (seconds) |

### Rollout Phases

1. **Phase 1** — `MCP_MODE=read`: read-only access
2. **Phase 2** — `MCP_MODE=write`: enable patches
3. **Phase 3** — `MCP_MODE=test`: enable Docker tests

**Never enable:** arbitrary shell, `git push`, `git reset`, `git rebase`, etc.

### Security Notes

- Do not commit `config.json`, `.env`, or API keys to Git
- Start with `read` mode; expand permissions after validation
- Perform `git push` manually, not via ChatGPT

### References

- [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [tunnel-client](https://github.com/openai/tunnel-client)
- [ChatGPT Developer Mode](https://help.openai.com/en/articles/12584461-developer-mode-apps-and-full-mcp-connectors-in-chatgpt-beta)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

---

## License

MIT
