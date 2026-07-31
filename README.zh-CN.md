# Local Repo MCP

<p align="right">
  <a href="./README.md">English</a> · <strong>简体中文</strong>
</p>

> 本地 **Secure Agent Coding Runtime**：策略、RBAC、Session、审批与沙箱写流程。可直接作为 MCP Server 供 Cursor / Claude Desktop 等客户端连接；如需接入 ChatGPT，可通过 [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) **可选** 启用 tunnel-client，无需暴露公网 MCP 入口。

**两种使用模式：**

| 模式 | 说明 |
|------|------|
| **纯 MCP**（默认） | 只启动 MCP Server，无需 tunnel-client |
| **ChatGPT 接入**（可选） | 勾选「启用 Tunnel」并配置 ID/Key 后，一键启动 Tunnel + MCP |

```text
# 纯 MCP
MCP 客户端 → Local Repo MCP → 本地仓库

# ChatGPT 接入（可选）
ChatGPT → Custom MCP App → Secure MCP Tunnel → tunnel-client → Local Repo MCP → 本地仓库
```

## 特性

- **Policy Engine** — 基于 `config/policy.yaml` 的读写/执行策略
- **Enterprise RBAC** — 策略文件中的用户/角色权限
- **Risk Scoring** — 高风险操作拦截并写入审计
- **Session 模型** — 写入与测试需先创建 Session
- **审批流程** — prepare → approve → apply
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
├── server.py              # 入口 shim
├── config/policy.yaml     # 策略、RBAC、风险阈值
├── src/
│   ├── mcp_app/server.py  # MCP 注册
│   ├── tools/             # read、patch、test、session
│   ├── security/          # policy_engine、rbac、risk、scanner
│   ├── session/
│   ├── repo/
│   ├── sandbox/
│   └── audit/
├── tests/                 # 安全验收测试
├── gui/
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
| [tunnel-client](https://github.com/openai/tunnel-client) | **可选** — 仅 ChatGPT 接入时需要 |

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

### 2. 使用 GUI（推荐 · 全操作在此完成）

**Windows：** 双击 `start_gui.bat`（自动创建 venv、安装依赖、打开控制面板）

```bash
python run_gui.py
```

GUI 四个标签页：

| 标签 | 功能 |
|------|------|
| **概览** | 一键启动 MCP / Tunnel+MCP（可选）、环境检查、快捷打开目录 |
| **本地组件** | MCP、venv、配置、Tunnel 等本地侧纳管（Tunnel 未启用时显示「可选」） |
| **Tunnel** | tunnel-client 安装、启停、Doctor（可选） |
| **配置** | 仓库、模式、RBAC、策略；可勾选「启用 ChatGPT Tunnel 接入」 |
| **运维** | Git 状态、Session 管理、Tunnel Doctor、安全测试 |
| **日志** | MCP / Tunnel / 审计实时日志 |

点击 **保存配置 · 同步策略** 会写入 `config.json`、`.env` 和 `config/policy.yaml`。

### 3. 命令行启动

```bash
export REPO_ROOT=/path/to/your/repo
export MCP_MODE=read
export POLICY_RULES=./config/policy.yaml
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
  → repo_approve_patch(patch, session_id)
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
| `repo_approve_patch` | write | 审批 patch |
| `repo_apply_patch` | write | 应用已审批 patch |
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
| `POLICY_RULES` | `./config/policy.yaml` | 策略文件路径 |
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

## 测试

```bash
python -m pytest tests/ -v
```

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
