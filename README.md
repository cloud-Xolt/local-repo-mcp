# Local Repo MCP

<p align="right"><strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a></p>

<p align="center"><strong>Safely connect one local Git repository to any MCP client.</strong></p>

<p align="center">
Read, search, inspect Git changes, apply validated text patches, and optionally run trusted tests—without exposing a general-purpose shell or your entire filesystem.
</p>

## Why this project?

Local Repo MCP solves one narrow problem:

> Give ChatGPT, Claude, Cursor, and other MCP clients enough access to work with one local Git repository, while keeping the permission boundary small and understandable.

It is deliberately **not** an enterprise agent platform, policy engine, RBAC service, or terminal agent.

## Highlights

- One configured Git repository only
- Read-only by default
- No general-purpose shell
- No unrestricted `write_file`
- Validated text-patch writes
- Filtered Git status and diff
- No Git push, pull, checkout, reset, rebase, merge, stash, or clean
- Optional predefined tests for trusted repositories
- STDIO and Streamable HTTP transports
- Optional OpenAI Secure MCP Tunnel
- Simplified Chinese and English GUI

## Architecture

### Local client with STDIO

```text
Local MCP client
      │
      │ starts a subprocess
      ▼
Local Repo MCP (STDIO)
      │
      ▼
One local Git repository
```

### URL-based client with Streamable HTTP

```text
MCP client
    │
    │ http://127.0.0.1:8000/mcp
    ▼
Local Repo MCP (Streamable HTTP)
    │
    ▼
One local Git repository
```

### ChatGPT with Secure MCP Tunnel

```text
ChatGPT
   │
OpenAI Secure MCP Tunnel
   │
tunnel-client
   │
Local Repo MCP (STDIO or HTTP)
   │
Local Git repository
```

## Tools

| Tool | Minimum mode | Description |
|---|---|---|
| `repo_list_files` | `read` | List allowed repository files |
| `repo_read_file` | `read` | Read one UTF-8 text file |
| `repo_search_code` | `read` | Fixed-string source-code search |
| `repo_git_status` | `read` | Filtered Git working-tree status |
| `repo_git_diff` | `read` | Filtered staged or unstaged diff |
| `repo_apply_patch` | `write` | Apply one validated unified text patch |
| `repo_run_test` | `test` | Run one predefined test command |

## Access modes

| Mode | Meaning |
|---|---|
| `read` | Read, search, Git status, and Git diff |
| `write` | Read tools plus validated patch application |
| `test` | Write tools plus predefined test commands |

Start with `read`.

## Transports

### STDIO

Use STDIO when the MCP client runs on the same machine and can launch a subprocess. STDIO has no host, port, or endpoint URL.

### Streamable HTTP

Use Streamable HTTP for clients that connect to an MCP URL or run in another process/device.

Default endpoint:

```text
http://127.0.0.1:8000/mcp
```

Security defaults:

- binds to `127.0.0.1`;
- built-in Host/Origin validation;
- optional Bearer Token;
- non-local binds require Bearer authentication and an explicit allowed-host list.

Do not bind to `0.0.0.0` without understanding the network exposure. Use HTTPS through a trusted reverse proxy for non-local deployments.

## Requirements

- Python 3.11+
- Git 2.39+
- ripgrep (`rg`)
- optional: OpenAI `tunnel-client`

Docker is not required.

## Install

```bash
git clone https://github.com/cloud-Xolt/local-repo-mcp.git
cd local-repo-mcp
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run_gui.py
```

Linux / macOS:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run_gui.py
```

## GUI

The GUI has five focused pages:

1. **Home** — repository, access mode, transport, and common settings
2. **MCP Server** — process status, real MCP handshake test, and client configuration
3. **ChatGPT Connection** — Secure MCP Tunnel setup and diagnostics
4. **Logs** — MCP, Tunnel, and audit logs
5. **About** — scope, version, documentation, and project links

Common settings stay visible. Limits, dirty-worktree behavior, audit logging, and HTTP allowlists are collapsed under **Advanced Settings**.

The GUI stores normal configuration under the current user's config directory. The OpenAI runtime API key is memory-only and is never written to disk. An HTTP Bearer token, when enabled, is stored separately with restrictive file permissions.

## Run without the GUI

### STDIO

Linux / macOS:

```bash
export REPO_ROOT="/absolute/path/to/repository"
export MCP_MODE="read"
export MCP_TRANSPORT="stdio"
python server.py
```

Windows PowerShell:

```powershell
$env:REPO_ROOT = "C:\absolute\path\to\repository"
$env:MCP_MODE = "read"
$env:MCP_TRANSPORT = "stdio"
python server.py
```

Example local-client configuration:

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

Connect to:

```text
http://127.0.0.1:8000/mcp
```

Bearer authentication:

```bash
export HTTP_AUTH_MODE="bearer"
export HTTP_AUTH_TOKEN="replace-with-a-random-token"
```

## Real connection test

The GUI connection test does not merely check that a directory exists. It:

1. creates an MCP client session;
2. performs protocol initialization;
3. lists the tools;
4. verifies the expected read tools;
5. calls `repo_git_status`;
6. closes the session cleanly.

For STDIO it launches a temporary child process. For HTTP it connects to the running endpoint.

## ChatGPT and Secure MCP Tunnel

Install `tunnel-client` from an official OpenAI source. This project does not download or update it automatically.

STDIO profile example:

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

The GUI can detect the executable, initialize a profile, run Doctor, and start/stop the Tunnel. The runtime API key remains in memory only.

For HTTP Tunnel mode, start the HTTP MCP server first. Automatic HTTP Tunnel setup currently supports an unauthenticated localhost endpoint; for custom Bearer-authenticated HTTP Tunnel setups, configure `tunnel-client` manually or use STDIO Tunnel.

## Configuration

### Core

| Variable | Default | Description |
|---|---:|---|
| `REPO_ROOT` | `.` | The single repository root |
| `MCP_MODE` | `read` | `read`, `write`, or `test` |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http` |
| `MAX_FILE_BYTES` | `200000` | Maximum readable file size |
| `MAX_PATCH_BYTES` | `200000` | Maximum patch size |
| `MAX_SEARCH_RESULTS` | `50` | Search result limit |
| `MAX_OUTPUT_BYTES` | `20000` | Diff/test output limit |
| `ALLOW_DIRTY_WORKTREE` | `false` | Allow patching a dirty worktree |
| `AUDIT_LOG` | empty | Optional audit JSONL path |
| `TEST_TIMEOUT_MAX` | `300` | Maximum test timeout |

### HTTP

| Variable | Default | Description |
|---|---:|---|
| `HTTP_HOST` | `127.0.0.1` | Bind address |
| `HTTP_PORT` | `8000` | Listen port |
| `HTTP_PATH` | `/mcp` | MCP endpoint path |
| `HTTP_AUTH_MODE` | `none` | `none` or `bearer` |
| `HTTP_AUTH_TOKEN` | empty | Bearer token |
| `HTTP_ALLOWED_HOSTS` | localhost values | Host allowlist |
| `HTTP_ALLOWED_ORIGINS` | localhost values | Origin allowlist |
| `HTTP_JSON_RESPONSE` | `true` | JSON response mode |
| `HTTP_STATELESS` | `true` | Stateless HTTP mode |
| `HTTP_MAX_REQUEST_BYTES` | `262144` | Maximum request body |

## Security model

The project is designed for one local user and one configured Git repository.

Controls include:

- relative paths only;
- parent traversal rejected;
- symbolic links rejected;
- common sensitive files blocked;
- binary/non-UTF-8 reads rejected;
- fixed-string `ripgrep` invocation with `shell=False`;
- blocked paths filtered from Git status and diff;
- text-patch-only writes;
- binary, rename, copy, submodule, symlink, and mode-change patches rejected;
- common credential patterns blocked in added patch lines;
- bounded inputs and outputs;
- no general-purpose shell;
- no automatic branch, commit, or push operations.

Limitations:

- common credential detection is not a complete secret scanner;
- write mode modifies the current worktree;
- test mode executes repository code and must be used only with trusted repositories;
- the MCP client controls user-facing confirmations;
- users should inspect `git diff`, commit, and push manually.

See [SECURITY.md](./SECURITY.md).

## Predefined tests

| Key | Command |
|---|---|
| `python_pytest` | `python -m pytest -q` |
| `go_test` | `go test ./...` |
| `node_test` | `npm test --` |
| `node_lint` | `npm run lint --` |
| `maven_test` | `mvn test` |
| `gradle_test` | `./gradlew test` |

Users cannot provide arbitrary commands or additional command arguments.

## Development

```bash
python -m pytest tests/ -v
python -m compileall server.py launch_mcp.py run_gui.py src gui
```

## Project scope

In scope:

- one local Git repository;
- safe reading and search;
- filtered Git inspection;
- validated text patches;
- optional predefined tests;
- STDIO and Streamable HTTP;
- optional GUI and Secure MCP Tunnel.

Out of scope:

- arbitrary shell access;
- general filesystem access;
- RBAC and multi-user hosting;
- enterprise policy engines or risk scoring;
- automatic branch management;
- automatic commit, merge, or push;
- cloud execution and untrusted-code sandboxing;
- automatic `tunnel-client` installation.

## License

MIT License. See [LICENSE](./LICENSE).
