# Local Repo MCP 1.3.0

[English](README.md) | [简体中文](README.zh-CN.md)

A focused, security-oriented MCP server for exactly one configured Git repository.

## Capabilities

- Seven fixed MCP tools for file listing, UTF-8 reads, fixed-string search, filtered Git status/diff, validated unified patches, and predefined tests.
- Three permission modes: `read`, `write`, and `test`.
- STDIO, OpenAI Secure MCP Tunnel, and Streamable HTTP transports.
- Remote HTTP through native HTTPS/mTLS or a trusted TLS-terminating reverse proxy.
- Bearer authentication, Host/Origin restrictions, bounded requests and outputs, sensitive-path filtering, audit records, and cross-process repository mutation locking.
- Desktop GUI with automatic configuration persistence. STDIO uses **Connect**; HTTP uses **Start/Stop**.
- Structured log center with MCP, Tunnel, Audit, and Security views; searchable readable summaries, raw JSON details, live refresh, credential redaction, and bounded rotation.

## Start from a source checkout

Windows:

```powershell
start_gui.bat
```

Linux/macOS:

```bash
./start_gui.sh
```

The bootstrap script creates `.venv` and refreshes dependencies whenever `requirements.txt` changes.

## Package entry points

```bash
pip install .
local-repo-mcp-gui
local-repo-mcp
```

Installed and source-checkout layouts both use the packaged `mcp_app.launcher`; they do not depend on a repository-root wrapper being present.

## Remote HTTP

Remote HTTP is not cloud-specific. It supports self-hosted servers, VMs, containers, Kubernetes, reverse proxies, and cloud load balancers.

Use either:

1. Native TLS with `HTTP_TLS_CERTFILE` and `HTTP_TLS_KEYFILE`; optionally set `HTTP_TLS_CLIENT_CA` for mTLS.
2. A trusted TLS reverse proxy with `HTTP_TLS_TERMINATED_PROXY=true`, `HTTP_PUBLIC_URL=https://host/mcp`, and explicit `HTTP_PROXY_TRUSTED_IPS`.

Wildcard bindings such as `0.0.0.0` are supported, but require an HTTPS `HTTP_PUBLIC_URL` whose path matches `HTTP_PATH`.

See `docs/DEPLOYMENT.md` and `docs/SECURITY.md`.

## Tests

```bash
python -m pytest -q -p no:cacheprovider
```

Local Repo MCP never performs checkout, commit, reset, rebase, merge, pull, or push.

## Documentation

- [Complete usage guide](docs/USAGE.md) — installation, first launch, STDIO, Secure MCP Tunnel, Streamable HTTP, logs, testing, and troubleshooting.
- [Deployment guide](docs/DEPLOYMENT.md) — native HTTPS, mTLS, reverse proxies, systemd, containers, and Kubernetes.
- [Security model](docs/SECURITY.md) — repository boundary, HTTP controls, secrets, logs, and trusted test execution.
- [Security policy](SECURITY.md) — supported security boundary and issue reporting.

## Requirements

- Python 3.11 or newer.
- Git available on `PATH`.
- One local Git working tree to expose.
- `tunnel-client` only when using OpenAI Secure MCP Tunnel.

## Permission modes

| Mode | Read/list/search/status/diff | Apply validated patch | Run predefined tests |
| --- | --- | --- | --- |
| `read` | Yes | No | No |
| `write` | Yes | Yes | No |
| `test` | Yes | Yes | Yes |

Test mode executes repository code with the current operating-system user's permissions. It is not a sandbox and must be enabled only for trusted repositories.

## MCP tools

| Tool | Purpose |
| --- | --- |
| `repo_list_files` | List allowed files under the configured repository. |
| `repo_read_file` | Read one allowed UTF-8 text file. |
| `repo_search_code` | Perform bounded fixed-string repository search. |
| `repo_git_status` | Return filtered Git worktree status. |
| `repo_git_diff` | Return a bounded, filtered Git diff. |
| `repo_apply_patch` | Apply one validated unified text patch. |
| `repo_run_test` | Run one predefined test command in `test` mode. |

## First-use workflow

1. Start the GUI.
2. Select the target Git working tree.
3. Choose `read`, `write`, or `test` mode.
4. Choose STDIO or Streamable HTTP.
5. For STDIO, select **Connect** to verify MCP initialize, tool discovery, and repository identity.
6. For HTTP, configure the Bearer token, select **Start**, and then select **Connect**.
7. Copy the generated client configuration from the **MCP Server** page.

The [complete usage guide](docs/USAGE.md) contains the full STDIO, Tunnel, HTTP, logging, testing, and troubleshooting procedures.

## ChatGPT and other MCP clients

Local Repo MCP can let ChatGPT build and maintain a local Git project within the selected permission mode. It is not limited to ChatGPT: other MCP-compatible coding agents, IDEs, desktop clients, and automation platforms can connect through STDIO or Streamable HTTP and receive the same tools and security controls.

For a new local project, initialize an empty directory with `git init`, select it in the GUI, and use `write` or `test` mode. See [Client compatibility and local project workflow](docs/CLIENTS.md).


Current GUI behavior: selecting a plain folder triggers a Git check and an explicit confirmation dialog. Accepting runs `git init`; declining leaves the folder unchanged. Initialization is never silent and does not create commits or remotes. A selected child directory inside a parent Git working tree cannot become a separate security boundary; the GUI asks to switch to the actual Git working-tree root.
