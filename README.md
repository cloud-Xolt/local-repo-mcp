# Local Repo MCP

<p align="right">
  <strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a>
</p>

> Secure local Git repository access for ChatGPT via [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) — no public MCP endpoint required.

```text
ChatGPT → Custom MCP App → Secure MCP Tunnel → tunnel-client → Local Repo MCP → Local Repo
```

## Features

- **Policy Engine** — read/write/execute rules via `security/rules.yaml`
- **Session model** — write and test operations require an active session
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

## Requirements

| Dependency | Purpose |
|------------|---------|
| Python 3.11+ | MCP Server runtime |
| Git 2.39+ | Repository operations |
| ripgrep (`rg`) | Code search |
| Docker | Test sandbox execution |
| [tunnel-client](https://github.com/openai/tunnel-client) | ChatGPT integration |

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

### 2. GUI (Recommended)

**Windows:** double-click `start_gui.bat`

```bash
python run_gui.py
```

The GUI exposes all settings: repo path, mode, policy file, sessions file, protected branches, write deny rules, test allowlist, Docker sandbox limits, and Tunnel credentials.

**Save Config** writes `config.json`, `.env`, and `rules.yaml`.

### 3. CLI

```bash
export REPO_ROOT=/path/to/your/repo
export MCP_MODE=read
export POLICY_RULES=./security/rules.yaml
export AUDIT_LOG=./audit.log

python server.py
```

## ChatGPT Integration

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
| `repo_apply_patch` | write | Apply patch |
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
| `POLICY_RULES` | `./security/rules.yaml` | Policy rules file |
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
