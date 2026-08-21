# Local Repo MCP 1.4.0

[English](README.md) | [简体中文](README.zh-CN.md)

A focused, security-oriented MCP server for exactly one configured Git repository.

**Primary constraint:** provide only controlled repository access, allowlisted test/build/check execution, and verifiable result return. Keep the server lightweight, single-repository, and fixed-surface; do not evolve it into an Agent, orchestration platform, or general remote shell.

## Capabilities

- Seven fixed MCP tools for file listing, UTF-8 reads, fixed-string search, filtered Git status/diff, atomic unified patches, and allowlisted verification commands.
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

On headless hosts (SSH/servers) use the interactive CLI instead of the GUI:

```bash
chmod +x start_cli.sh
./start_cli.sh
```

The bootstrap script creates `.venv` and refreshes dependencies whenever `requirements.txt` changes.

## Package entry points

```bash
pip install .
local-repo-mcp-gui
local-repo-mcp-cli
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

Local Repo MCP never performs checkout, reset, rebase, merge, pull, push, or amend. Local `git commit` is off by default and requires an explicit GUI/`ALLOW_GIT_COMMIT` enablement in write or test mode.

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

| Mode | Read/list/search/status/diff | Apply validated patch | Optional local commit | Run allowlisted verification commands |
| --- | --- | --- | --- | --- |
| `read` | Yes | No | No | No |
| `write` | Yes | Yes | Yes when enabled | No |
| `test` | Yes | Yes | Yes when enabled | Yes |

Test mode executes repository code with the current operating-system user's permissions. It is not a sandbox and must be enabled only for trusted repositories.

## MCP tools

| Tool | Purpose |
| --- | --- |
| `repo_list_files` | List allowed files under the configured repository. |
| `repo_read_file` | Read one allowed UTF-8 text file; PNG/JPEG return as MCP image content. |
| `repo_search_code` | Perform bounded fixed-string repository search. |
| `repo_git_status` | Return filtered Git worktree status. |
| `repo_git_diff` | Return a bounded, filtered Git diff. |
| `repo_apply_patch` | Atomically apply one validated unified text patch; one patch may modify multiple files, and any target failure prevents the whole patch from applying. |
| `repo_git_commit` | Create one local Git commit for allowlisted pending changes when `ALLOW_GIT_COMMIT` is enabled; optional `paths` limits the staged set. |
| `repo_run_test` | Run one or a bounded batch of allowlisted test/build/lint/check commands in `test` mode and return verifiable exit/output evidence. |

`repo_run_test` keeps its historical tool name for client compatibility while delegating execution to the controlled command layer. The default allowlist includes `python_pytest`, `go_test`, `go_build`, `go_vet`, `node_test`, `node_build`, `node_lint`, `maven_test`, `maven_build`, `gradle_test`, and `gradle_build`.

Use `command_key` for one command. Use `command_keys` for a sequential batch of at most 8 commands. The complete batch is allowlist-validated before the first command starts; `stop_on_failure=true` stops on the first failure, while `false` continues through the remaining commands. This is bounded in-call execution, not a queue, scheduler, or background task system.

Every started command returns normalized evidence: command identity/kind, `status`, `success`, `exit_code` (with compatibility `returncode`), stdout/stderr plus truncation flags, and duration/timeout metadata. Timeout or output-limit termination remains a structured failed result with captured output. Command lifecycle metadata is logged, but stdout/stderr are not written to runtime/audit logs.

All eight public tools publish typed MCP input and output contracts. The server relies on MCP SDK structured-output generation instead of client-specific schema patches; GUI connection verification rejects missing/invalid tool schemas before accepting a connection. Optional collection inputs are represented as optional parameters with non-null array schemas rather than nullable unions.

`src/tools/contracts.py` is the single protocol-contract module for the public tool surface. Protocol regressions are tested against the actual `MCPServer.list_tools()` result, including the fixed eight-tool surface and presence of `outputSchema` for every tool.

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

For a new local project, select an empty directory in the GUI, explicitly confirm Git initialization, and use `write` or `test` mode. See [Client compatibility and local project workflow](docs/CLIENTS.md).


Current GUI behavior: selecting a plain folder triggers a Git check and an explicit confirmation dialog. Accepting runs `git init`; declining leaves the folder unchanged. Initialization is never silent and does not create commits or remotes. A selected child directory inside a parent Git working tree cannot become a separate security boundary; the GUI asks to switch to the actual Git working-tree root.
