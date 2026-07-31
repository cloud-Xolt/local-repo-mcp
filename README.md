# Local Repo MCP

<p align="right">
  <strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a>
</p>

> **Secure Agent Coding Runtime** for local Git repos: policy, RBAC, sessions, approval workflow, and sandboxed writes. Run as a standalone MCP Server for Cursor / Claude Desktop, etc. **Optionally** connect ChatGPT via [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) and tunnel-client — no public MCP endpoint required.

**Two modes:**

| Mode | Description |
|------|-------------|
| **MCP only** (default) | Start MCP Server only; tunnel-client not required |
| **ChatGPT** (optional) | Enable Tunnel in Settings, configure ID/Key, then start Tunnel + MCP |

```text
# MCP only
MCP client → Local Repo MCP → local repo

# ChatGPT (optional)
ChatGPT → Custom MCP App → Secure MCP Tunnel → tunnel-client → Local Repo MCP → local repo
```

## Features

- **Policy Engine** — read/write/execute rules via `config/policy.yaml`
- **Enterprise RBAC** — user/role permissions in policy file
- **Risk Scoring** — high-risk operations blocked and scored in audit logs
- **Session model** — write and test operations require an active session
- **Approval workflow** — prepare → approve → apply for patches
- **Git branch sandbox** — protected branches auto-switch to `agent/{session_id}`
- **Path sandbox** — all operations confined to `REPO_ROOT`
- **Secret scanning** — blocks credentials in patches before apply
- **Docker test sandbox** — isolated containers (no network, read-only mount)
- **Prompt injection mitigation** — file content wrapped as `UNTRUSTED_DATA`
- **Audit logging** — structured logs with sensitive data redaction
- **GUI control panel** — full configuration, one-click start and monitoring

## Project Structure

```text
local-repo-mcp/
├── server.py              # entry shim
├── config/policy.yaml     # policy, RBAC, risk thresholds
├── src/
│   ├── mcp_app/server.py  # MCP registration
│   ├── tools/             # read, patch, test, session tools
│   ├── security/          # policy_engine, rbac, risk, scanner
│   ├── session/
│   ├── repo/
│   ├── sandbox/
│   └── audit/
├── tests/                 # security acceptance tests
├── gui/
├── run_gui.py
├── start_gui.bat
├── requirements.txt
├── .env.example
└── systemd/
```

## Requirements

| Dependency | Purpose |
|------------|---------|
| Python 3.11+ | MCP Server runtime |
| Git 2.39+ | Repository operations |
| ripgrep (`rg`) | Code search |
| Docker | Test sandbox execution |
| [tunnel-client](https://github.com/openai/tunnel-client) | **Optional** — only for ChatGPT integration |

## Quick Start

### 1. Install

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

### 2. GUI (Recommended — all operations in-app)

**Windows:** double-click `start_gui.bat` (auto-creates venv, installs deps, opens the panel)

```bash
python run_gui.py
```

Four tabs:

| Tab | Purpose |
|-----|---------|
| **Overview** | One-click MCP / Tunnel+MCP start, env check, quick folder open |
| **Settings** | Repo, mode, RBAC, policy, Tunnel, sandbox — full configuration |
| **Operations** | Git status, session management, Tunnel doctor/init, security tests |
| **Logs** | Live MCP / Tunnel / audit stream |

**Save Config** writes `config.json`, `.env`, and `config/policy.yaml`.

### 3. CLI

```bash
export REPO_ROOT=/path/to/your/repo
export MCP_MODE=read
export POLICY_RULES=./config/policy.yaml
export AUDIT_LOG=./audit.log

python server.py
```

## ChatGPT Integration (Optional)

### Prerequisites

1. ChatGPT workspace with Developer Mode enabled
2. Tunnel created on OpenAI Platform and linked to your workspace
3. `tunnel-client` installed

### Initialize Tunnel

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

### Create Custom MCP App

In ChatGPT: **Apps → Create developer-mode app → Connection: Tunnel → Scan Tools → Create**

## Recommended Workflow

```text
repo_session_start(user, permission="write")
  → repo_prepare_patch(patch, session_id)
  → repo_approve_patch(patch, session_id)
  → repo_apply_patch(patch, session_id)
  → repo_run_test(command_key, session_id)
  → repo_session_end(session_id)
```

## MCP Tools

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
| `repo_approve_patch` | write | Approve patch for apply |
| `repo_apply_patch` | write | Apply approved patch |
| `repo_run_test` | test | Run test in Docker sandbox |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REPO_ROOT` | `.` | Repository root |
| `MCP_MODE` | `read` | `read` / `write` / `test` / `ship` |
| `MAX_FILE_BYTES` | `200000` | Max file read size (bytes) |
| `MAX_PATCH_BYTES` | `200000` | Max patch size (bytes) |
| `ALLOW_DIRTY_WORKTREE` | `false` | Allow patch on dirty worktree |
| `AUDIT_LOG` | `./audit.log` | Audit log path |
| `POLICY_RULES` | `./config/policy.yaml` | Policy rules file |
| `SESSIONS_FILE` | `./sessions.json` | Session storage path |
| `SANDBOX_MEMORY` | `2g` | Docker sandbox memory |
| `SANDBOX_CPUS` | `2` | Docker sandbox CPUs |
| `SANDBOX_TMPFS_MB` | `512` | Sandbox tmpfs size (MB) |
| `TEST_TIMEOUT_MAX` | `300` | Max test timeout (seconds) |

See [`.env.example`](./.env.example) for a full template.

## Rollout Phases

| Phase | Mode | Capabilities |
|-------|------|--------------|
| 1 | `read` | List, read, search, git status/diff |
| 2 | `write` | + patch prepare/apply |
| 3 | `test` | + Docker sandbox tests |

**Never enable:** arbitrary shell, `git push`, `git reset`, `git rebase`, etc.

## Tests

```bash
python -m pytest tests/ -v
```

## Security Notes

- Do not commit `config.json`, `.env`, or API keys to Git
- Start with `read` mode; expand permissions after validation
- Perform `git push` manually, not via ChatGPT

## Linux Deployment

See [`systemd/`](./systemd/) for service unit examples. Run as a low-privilege user (e.g. `repo-mcp`).

## References

- [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [tunnel-client](https://github.com/openai/tunnel-client)
- [ChatGPT Developer Mode](https://help.openai.com/en/articles/12584461-developer-mode-apps-and-full-mcp-connectors-in-chatgpt-beta)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## License

MIT
